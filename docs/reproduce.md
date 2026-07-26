# Reproduce

Last updated: 2026-07-26 14:05:41 Asia/Bangkok

All heavy work runs on the VM. Do not install project dependencies, run tests, train models, Docker, Terraform, or `gcloud` locally.

```bash
git switch feat/onemount-property-intelligence
make remote-doctor
make remote-bootstrap
make remote-sync
make remote-verify
```

Additional targets required by the contract:

```bash
make remote-etl-smoke
make remote-train-smoke
make remote-reproduce-smoke
make remote-reproduce-full
make remote-up
make remote-cloud-smoke
```

Cloud reproduction is blocked until the VM service account has sufficient OAuth scopes/IAM for project `driven-reef-452414-b5`.

Docker reproduction is blocked until user `ducan` can access `/var/run/docker.sock` and a Compose command is available on the VM.
