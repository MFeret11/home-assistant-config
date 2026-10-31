# ==============================================================================
# PYSCRIPT MODULE: HARDWARE SAFETY INTERLOCKS
# ==============================================================================
# The long-running safety tasks that open projector and Batocera mains.
#
# They live here, apart from theater.py, because pyscript reloads a file as
# soon as it is saved and a reload kills that file's running tasks. Editing
# theater.py (art lookups, modes, audio) no longer cancels a cooldown in
# progress, and a broken theater.py save leaves these running.
#
# This file must not depend on theater.py. theater.py calls these as services:
#   pyscript.safe_projector_cooldown     (interlock 1, manual use only since 2026-10-29)
#   pyscript.cancel_projector_cooldown   (a new session starts)
#   pyscript.shutdown_batocera           (interlock 2, clean software halt)
# batocera_auto_power_off below opens the Batocera relay (interlock 2), and
# projector_stray_wake_guard puts a lamp lit with nobody in the theater back
# into standby over CEC (it never cuts mains).
#
# Change this file rarely, with the theater idle, and read
# docs/safety-interlocks.md first.
# ==============================================================================
import time

BOOT_TIMESTAMP = time.time()

PROJECTOR_SWITCH = "switch.projector"
PROJECTOR_CURRENT = "sensor.projector_current"
BATOCERA_SWITCH = "switch.batocera"
BATOCERA_CURRENT = "sensor.batocera_current"
BATOCERA_STATE = "sensor.batocera_state"
THEATER_MODE = "sensor.theater_mode"
THEATER_IN_USE = "binary_sensor.theater_in_use"
RECEIVER = "media_player.theater_receiver"
ONN_PRO = "media_player.onn_pro"
ONN_REMOTE = "remote.onn_pro"

PROJECTOR_COLD_AMPS = 0.06      # fan stopped
PROJECTOR_LAMP_LIT_AMPS = 0.5   # lamp still on
BATOCERA_IDLE_AMPS = 0.05
COOLDOWN_LOCK_S = 90
COOLDOWN_POLL_S = 10
COOLDOWN_ATTEMPTS = 25
COOLDOWN_TASK = "projector_cooldown_worker"
STRAY_WAKE_RETRY_S = 60
NOTIFY_TITLE = "Theater projector"


# Small local copies of theater.py helpers, so this file stands alone.
def _get(entity_id, default=None):
    try:
        val = state.get(entity_id)
        return val if val is not None else default
    except Exception:
        return default


def _float(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def _call(service_func, **kwargs):
    try:
        service_func(**kwargs)
    except Exception as e:
        name = getattr(service_func, "__name__", str(service_func))
        log.warning(f"[Interlocks] service call failed: {name} {kwargs}: {e}")


def is_booting(grace_seconds=30) -> bool:
    return (time.time() - BOOT_TIMESTAMP) < grace_seconds


# ------------------------------------------------------------------------------
# INTERLOCK 1: PROJECTOR THERMAL CUTOFF
# ------------------------------------------------------------------------------
def _cec_standby_once():
    """Sleep the Onn (CEC standby) and drop the receiver. theater.py has its own
    multi-round version for session end; this is the cooldown's single retry."""
    if _get(ONN_PRO) == "on":
        _call(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
        _call(media_player.turn_off, entity_id=ONN_PRO)
        task.sleep(1.0)
    if _get(RECEIVER) == "on":
        _call(media_player.select_source, entity_id=RECEIVER, source="AUDIO1")
        task.sleep(0.5)
        _call(media_player.turn_off, entity_id=RECEIVER)
        task.sleep(2.0)


@service
def safe_projector_cooldown():
    """90s thermal lock, then cut projector mains only after 2 consecutive reads
    <= 0.06A. If that can't be verified, mains stay on so the fans keep cooling."""
    task.unique(COOLDOWN_TASK)
    _projector_cooldown_body()


@service
def cancel_projector_cooldown():
    """A new session is starting: stop a running cooldown."""
    task.unique(COOLDOWN_TASK)


def _projector_cooldown_body():
    if _get(PROJECTOR_SWITCH) != "on":
        return

    log.info("[Interlocks] Projector shutdown initiated. Commencing 90s thermal lock...")
    task.sleep(COOLDOWN_LOCK_S)

    fan_stopped = False
    consecutive_low_reads = 0

    for attempt in range(COOLDOWN_ATTEMPTS):
        mode = _get(THEATER_MODE)
        if mode in ["movie", "game", "sports"]:
            log.info("[Interlocks] Session resumed. Cooldown power cut cancelled.")
            return

        try:
            current_val = float(_get(PROJECTOR_CURRENT))
        except (ValueError, TypeError):
            consecutive_low_reads = 0
            log.warning(f"[Interlocks] Transient projector reading on attempt {attempt + 1}/{COOLDOWN_ATTEMPTS}. Retrying...")
            task.sleep(COOLDOWN_POLL_S)
            continue

        if current_val <= PROJECTOR_COLD_AMPS:
            consecutive_low_reads += 1
            if consecutive_low_reads >= 2:
                fan_stopped = True
                break
        else:
            consecutive_low_reads = 0
            # Lamp still lit: re-send CEC standby (twice total, ~110s and ~170s in)
            if current_val > PROJECTOR_LAMP_LIT_AMPS and attempt in (2, 8) and mode == "off":
                log.warning("[Interlocks] Lamp drawing >0.5A. Re-sending CEC standby...")
                _cec_standby_once()
                state.set(THEATER_MODE, value="off")
                state.set(THEATER_IN_USE, value="off")
            elif current_val > PROJECTOR_LAMP_LIT_AMPS and attempt in (2, 8) and mode == "music":
                # The Onn is playing the music: sleeping it takes the receiver down over CEC
                # and ends the session (2026-10-23). Leave the lamp; session end puts it out.
                log.warning("[Interlocks] Lamp still lit during music. Not sleeping the Onn; mains stay on.")

        task.sleep(COOLDOWN_POLL_S)

    if fan_stopped and _get(THEATER_MODE) in ["music", "off"]:
        log.info("[Interlocks] Cooldown double-verified. Cutting projector mains.")
        switch.turn_off(entity_id=PROJECTOR_SWITCH)
    else:
        log.warning("[Interlocks] Cooldown could not be verified. Projector mains left ON for safety.")


# ------------------------------------------------------------------------------
# STRAY WAKE GUARD
# ------------------------------------------------------------------------------
# Session end leaves the projector in standby (mains on) so CEC can wake it.
# Anything that wakes the Onn can then strike the lamp in an empty room. The
# receiver stays off on those wakes (scrcpy, updates), and a real session always
# turns it on, so: lamp lit for 2 minutes with the theater not in use = stray.
# This also catches a session end whose CEC standby didn't take.
def _notify(message):
    try:
        persistent_notification.create(title=NOTIFY_TITLE, message=message,
                                       notification_id="projector_stray_wake")
    except Exception as e:
        log.warning(f"[Interlocks] persistent notification failed: {e}")
    try:
        notify.ntfy(title=NOTIFY_TITLE, message=message)
    except Exception as e:
        log.warning(f"[Interlocks] ntfy failed: {e}")


def _lamp_lit_while_idle():
    return (_float(_get(PROJECTOR_CURRENT), 0.0) > PROJECTOR_LAMP_LIT_AMPS
            and _get(THEATER_IN_USE) == "off")


# 0.5 = PROJECTOR_LAMP_LIT_AMPS, 120s hold
@state_trigger("float(sensor.projector_current) > 0.5 and binary_sensor.theater_in_use == 'off'", state_hold=120)
def projector_stray_wake_guard():
    if is_booting():
        return
    task.unique("projector_stray_wake_guard")
    if not _lamp_lit_while_idle():
        return
    for attempt in range(2):
        if _get(ONN_PRO) != "on":
            # Not woken by the Onn (projector remote or front panel?): someone may be
            # there, and HA has no other way to send standby. Just say so.
            break
        log.warning(f"[Interlocks] Projector lamp lit with the theater not in use. CEC standby (try {attempt + 1}/2).")
        _call(remote.send_command, entity_id=ONN_REMOTE, command="SLEEP")
        _call(media_player.turn_off, entity_id=ONN_PRO)
        task.sleep(STRAY_WAKE_RETRY_S)
        if not _lamp_lit_while_idle():
            break
    if _get(THEATER_IN_USE) != "off":
        return  # a session started meanwhile; leave it alone
    if _lamp_lit_while_idle():
        _notify("The projector lamp is on but the theater isn't in use, and CEC standby didn't turn it off. Mains left on so it can cool.")
    else:
        _notify("The projector woke up with nobody using the theater. It's back in standby.")


# ------------------------------------------------------------------------------
# INTERLOCK 2: BATOCERA FILE SYSTEM SAFETY
# ------------------------------------------------------------------------------
def is_batocera_on():
    return (
        _get(BATOCERA_SWITCH) == "on"
        or _get(BATOCERA_STATE) in ["playing", "idle"]
        or _float(_get(BATOCERA_CURRENT), 0.0) >= BATOCERA_IDLE_AMPS
    )


@service
def shutdown_batocera():
    """Clean software shutdown, so the relay never cuts a running file system."""
    if not is_batocera_on():
        return
    log.info("[Interlocks] Batocera clean software shutdown dispatched.")
    for btn in ["button.batocera_shutdown_2", "button.batocera_shutdown"]:
        try:
            button.press(entity_id=btn)
            return
        except Exception:
            continue


@state_trigger("float(sensor.batocera_current) < 0.05", state_hold=12)
def batocera_auto_power_off():
    """Open the relay only after the draw has stayed under 0.05A for 12s (halted)."""
    if is_booting():
        return
    if _get(BATOCERA_SWITCH) == "on":
        switch.turn_off(entity_id=BATOCERA_SWITCH)
