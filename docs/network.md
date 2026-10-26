# Network Topology & Host Runtime

_Moved verbatim from AGENTS.md. "§N" references point to the old AGENTS.md sections (§4 lighting/sports now live in docs/lighting.md)._

## 1. System Runtime & Network Topology
- **Host**: Raspberry Pi 4 Model B (Crucial BX500 240GB SATA SSD [CT240BX500SSD1, SM2258XT/59XT DRAM-less, 80 TBW endurance] inside Sabrent 2.5" Tool-Free Enclosure [EC-UASP, JMicron JMS578 bridge, UASP SATA III over USB 3.0], active fan ~37.4°C).
- **HA Core**: Home Assistant Container using named volume `ha_config:/config` (`network_mode: host`).
- **Database & Recorder**: SQLite internal (`/config/home-assistant_v2.db`). Tuned for Crucial BX500 DRAM-less SSD health on Sabrent UASP bridge: `purge_keep_days: 7`, `commit_interval: 15` (batched commits minimizing Write Amplification Factor on DRAM-less NAND and eliminating USB bus reset timeouts), `auto_purge: true`, `auto_repack: true`. Raw ADC micro-jitter (`sensor.projector_current`, `sensor.batocera_current`) and 1Hz playback ticker (`sensor.mediasession2mqtt_1_playback_position`) are excluded to suppress 7,269 raw jitter events (93.3% write reduction). High-value usage telemetry (`media_player.theater_receiver`, `media_player.theater_onn_pro_adb`, `sensor.projector_current_rounded`, `sensor.projector_power_state`) is explicitly preserved for historical reporting and automations.
- **SSD Health (SMART)**: `smartd` on the host watches the BX500, and `ssd-health-report` (systemd timer: daily at 05:10 and ~10 min after boot, plus a smartd hook on problems) POSTs `smartctl` results to an HA webhook (`!secret ssd_health_webhook_id`, LAN-only). `packages/ssd_health.yaml` turns them into `sensor.ssd_life_remaining`, `sensor.ssd_temperature`, `sensor.ssd_last_health_report`, `binary_sensor.ssd_health_problem` and `binary_sensor.ssd_health_report_stale` (no report for 50h), and alerts via `notify.ntfy`. Host-side files and installer: `~/docker/ssd-health/` (not in this repo). Shown on the Diagnostics System Health card.
- **Zigbee Coordinator**: Sonoff Zigbee 3.0 Dongle Plus MG24 (Silicon Labs EFR32MG24) mapped to `/dev/ttyUSB0` via `/dev/serial/by-id/usb-SONOFF_SONOFF_Dongle_Plus_MG24_3852be1b41f5ef11a70499a29ed47d52-if00-port0`.
- **Live TV Proxy**: xTeVe container on port 34400 (replaces Threadfin due to Pi 4 compatibility; zero-transcode M3U proxy passing raw ATSC MPEG-2/AC-3 from HDHomeRun).
  - Guide: xTeVe reads a filtered local XMLTV file (`/epg/us_locals_philly.xml`, ~800 KB), not the full epgshare01 US Locals feed (~560 MB, which cost ~2 GB RAM). `~/docker/xteve/epg_filter.py` rebuilds it nightly at 23:30 (cron), keeping only stations in the HDHomeRun lineup. If the guide goes stale, check `~/docker/xteve/epg/filter.log`.
  - Threadfin note: its `:latest` Docker tag is amd64-only; version tags (e.g. `1.2.37`) include arm64.
  - Config lives in the named volume `septa-project_xteve_conf` mounted at `/home/xteve/conf`.
- **Alert Channel**: `notify.ntfy` (ntfy.sh push notifications), a REST notifier defined in `packages/ntfy.yaml`; the topic is `ntfy_topic` in `secrets.yaml`. Title and message only: per-call priority/tags are not forwarded.
- **Subnet Route**: Pi advertises `192.168.1.221/32` (HDHomeRun tuner) over Tailscale (`100.82.195.2`). Remote users access raw MPEG-2 stream via xTeVe M3U. In the basement theater, the native HDHomeRun app (`com.silicondust.view`) is used directly on Onn 4K Pro. SSH/HA/Portainer blocked at WireGuard layer.
- **Secrets**: API keys (TMDB, SteamGridDB, RAWG) and device credentials live in `secrets.yaml`. Never inline credentials in this doc, dashboards, or pyscript.

| Device / Host | IP Address | Interface / MAC | Protocol / Ports | Notes |
|---|---|---|---|---|
| RPi 4 (Docker Host) | `192.168.1.x` / `100.82.195.2` | Eth / `tailscale0` | 8123 (HA), 34400 (xTeVe), 9000 (Portainer), 8000 (Transit) | Docker stack: `~/docker/docker-compose.yml` (xTeVe used over Threadfin for Pi 4) |
| HDHomeRun FLEX DUO | `192.168.1.221` | Static DHCP | 80 (HTTP), 5004 (RTSP/MPEG-TS) | 2x ATSC 1.0 tuners, mDNS `hdhomerun.local` |
| Onn 4K Pro (Android TV) | `192.168.1.216` | Ethernet | ADB / Cast / Android TV Remote | Primary theater streamer (HDHomeRun, Stremio, YouTube, Spotify) |
| Yamaha RX-V673 AVR | `192.168.1.250` | Ethernet | Native `yamaha` Core Integration | 5.1 AVR (HDMI1: Onn, HDMI2: Batocera, HDMI3: Switch) |
| Batocera x86 PC | `192.168.1.220` (Eth) / `.190` (WiFi) | Dual NIC | SSH / Web (credentials in `secrets.yaml`) | EmulationStation / RetroArch; also runs the Moonlight client that streams the ROG Gaming PC |
| ASUS ROG Gaming PC | `192.168.1.205` | Ethernet | WOL / RDP | Dedicated PC gaming; streamed to the theater through Moonlight on Batocera |
| Transit Microservice | `localhost:8000` | Host Network | HTTP (FastAPI) | `Good_Morning_Dashboard` container |

