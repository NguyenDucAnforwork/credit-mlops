# Remote Environment

Last updated: 2026-07-26 20:09:20 Asia/Bangkok

## SSH

- Host: `lfm`
- Required workspace: `/home/ducan/credit-mlops-codex`
- Preflight command: `ssh -o BatchMode=yes -o ConnectTimeout=10 lfm 'printf "SSH_OK\n"; whoami; hostname; pwd'`
- Result: `SSH_OK`, user `ducan`, hostname `lfm`, home `/home/ducan`

## VM Resources

- OS: Ubuntu 24.04.4 LTS
- CPU: 4 vCPU, AMD EPYC 7B12, x86_64
- Memory: 15 GiB total, 14 GiB available during preflight
- Disk `/`: 145 GiB total, 80 GiB used, 66 GiB available
- GPU: not present (`nvidia-smi` not found)

## Tools

- `git`: `/usr/bin/git`
- `docker`: `/usr/bin/docker`
- `gcloud`: `/snap/bin/gcloud`
- `python3`: Python 3.12.3
- `terraform`: not found during preflight
- `uv`: installed later at `/home/ducan/.local/bin/uv`
- Docker client: 29.1.3
- Docker server access: blocked for user `ducan`
- Docker Compose: `docker compose` unavailable
- Latest measured Python suite: 139 tests passed in 12.15 seconds on the VM after remote smoke reproduction work.
- Latest remote smoke reproduction: `make remote-reproduce-smoke` completed in 8 seconds with 61 focused tests passing in 4.86 seconds.
- Latest measured local VM HTTP benchmark: AVM p95 140.84 ms and lending p95 24.21 ms with 0% errors at 1,000 requests/concurrency 10.
- Latest startup warm-up benchmark: property index startup 4.85 seconds, first comparable request after startup 10.99 ms.
- Latest AVM artifact evidence: 2.37 MB remote-only joblib, load 87.13 ms, single prediction 21.32 ms, same-seed MdAPE delta 0.0 percentage points.
- Latest artifact-backed local VM HTTP benchmark: AVM p95 136.63 ms and lending p95 15.53 ms with 0% errors at 1,000 requests/concurrency 10.

## Docker Access

- User/group: `uid=1002(ducan) gid=1003(ducan)`
- Groups: `ducan adm dialout cdrom floppy audio dip video plugdev lxd netdev ubuntu google-sudoers`
- Socket: `/var/run/docker.sock` is owned by `root:docker` with mode `srw-rw----`
- Result: `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`
- Minimum blocker: add `ducan` to the `docker` group or provide another approved non-sudo Docker access path; install the Docker Compose plugin or compatible `docker-compose`.

## GCP Access

- Active account: `582914829900-compute@developer.gserviceaccount.com`
- Configured project: `driven-reef-452414-b5`
- Project describe: blocked by `ACCESS_TOKEN_SCOPE_INSUFFICIENT`
- Service Usage list: blocked by `ACCESS_TOKEN_SCOPE_INSUFFICIENT`

Minimum blocker for cloud phases: update VM OAuth access scopes and/or IAM so the VM service account can call Cloud Resource Manager and Service Usage for project `driven-reef-452414-b5`. No long-lived service account key should be downloaded as a workaround.
