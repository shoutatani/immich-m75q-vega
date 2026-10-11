# Run Immich on the M75q-1's Vega 11

English | [日本語](README.ja.md)

This setup enables Immich's **smart search, face detection and face feature extraction, and OCR** on the integrated GPU of a ThinkCentre M75q-1 with a Ryzen 5 PRO 3400GE.

It uses a standard Immich Docker Compose layout, with photos in `library` and the database in `postgres`. It does not include external HDD, external library, or cloud backup configuration. The machine learning image required for GPU support is built on the target machine.

**This is an unofficial setup specifically for Immich v3.3.1.** It includes compatibility settings for running an older Vega GPU with ROCm and GPU libraries; OCR uses Immich 3.3.1's official implementation. It is not a migration or upgrade tool for existing Immich installations.

> **Updates during operation:** This repository is pinned to the hardware-validated Immich v3.3.1 release. Keep checking for stable releases and security fixes. Back up photos and the database, follow the official upgrade instructions, and check compatibility with the custom GPU libraries. Verify GPU inference and OCR in an isolated environment before applying a new version. This installer does not automatically update versions or migrate an existing v3.2.0 installation.

## Requirements

- ThinkCentre M75q-1 with a Ryzen 5 PRO 3400GE and integrated Radeon Vega 11 (gfx902).
- Ubuntu 24.04 LTS / x86_64. The test machine runs Linux 6.8 and has 32 GB of RAM.
- Both `/dev/kfd` and `/dev/dri/renderD128` must be present.
- Docker Engine and Docker Compose v2, with permission to run `docker info` as the current user.
- Python 3.11 or later, `curl`, `tar`, `dpkg-deb`, and `git`.
- Sufficient free space for Docker and the installation directory. At least 100 GiB is recommended, excluding photo storage.
- Network access to GitHub, AMD's package repositories, GHCR, and the model download services.

To install Docker, follow the [official Docker instructions for Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Run this setup as a regular user. It does not change the host GPU driver, kernel, or BIOS settings.

## Installation

Run these commands on the M75q-1. The GPU image is not built on a Mac.

```bash
git clone https://github.com/shoutatani/immich-m75q-vega.git
cd immich-m75q-vega
./setup.sh
```

Defaults:

| Setting | Value |
| --- | --- |
| Installation directory | `~/immich-app` |
| Browser access port | `2283` |
| Photos | `~/immich-app/library` |
| Database | `~/immich-app/postgres` |
| Compose project | `immich-m75q` |
| Model and GPU caches | A dedicated Docker volume for the project |
| OCR model | `PP-OCRv5_mobile` (Immich default) |
| Face recognition model | `buffalo_l` (Immich default) |
| Smart search model | `ViT-B-32__openai` (Immich default) |

The setup downloads dependencies, verifies their SHA256 checksums, builds the gfx900 libraries, creates the custom image, prepares face recognition, smart search, and OCR for their first GPU runs, and starts Immich. The first installation can take tens of minutes. Monitor the logs and allow time for model preparation to finish.

Once complete, open `http://YOUR-M75Q-1-IP:2283` and register an administrator as you would with a standard Immich installation. A database password is generated automatically and saved in the installation directory's `.env` file with owner-only access. The setup does not create an application administrator automatically.

To search for text visible in photos, select the **OCR** search type in Immich. Smart search is for finding photos by their content.

As with the standard configuration, the port listens on all network interfaces. Publishing the service to the internet is outside the scope of this repository.

### Use a different directory and port

```bash
./setup.sh install \
  --directory "$HOME/immich-gpu-test" \
  --project immich-gpu-test \
  --port 2294
```

Use a separate directory, project name, and port. The database, photos, network, and caches will also be separate. This setup does not use fixed container names or existing external volumes. The physical GPU, CPU, and memory are still shared with other workloads on the host, so concurrent heavy processing can cause resource contention.

The installer refuses to use a nonempty unmanaged directory, a project name belonging to another installation, or an occupied port. If a network request fails, rerun the same version of the source with the same options. The installer never automatically deletes photos or the database.

## Verification

First, check the status:

```bash
./setup.sh status
```

After registering an administrator, run the following command to verify the installation, including the application. It prompts for the administrator's email and password.

```bash
./setup.sh verify
```

This uploads sample images and **restarts this installation's machine learning container once**. Run it when no images are being processed. Results are saved to `evidence/verification.json` in the installation directory.

- Compare CPU and GPU OCR results using a fictional Japanese driver's license sample and a blank image.
- Check face detection, 512-dimensional face feature extraction, and smart search feature extraction using a face image.
- Check ONNX Runtime profiles for MIGraphX execution and zero CPU execution events for each model.
- Check uploads, stored OCR results, OCR search for `運転免許証` (driver's license), and stored face information.
- Restart the machine learning container, upload images with different checksums, and repeat the application checks.

For a new disposable test installation, you can create a test administrator automatically:

```bash
./setup.sh verify --directory "$HOME/immich-gpu-test" --initialize-test-admin
```

This option is intended for installations with no registered users. Credentials are saved to `test-admin-credentials.json` in the installation directory and are not printed in logs. The test images and account remain available for inspection.

## Everyday commands

If you use a custom installation directory, add `--directory` to each command.

Check container status:

```bash
./setup.sh status
```

View machine learning logs:

```bash
./setup.sh compose -- logs --tail 100 immich-machine-learning
```

Stop containers while retaining data:

```bash
./setup.sh compose -- stop
```

Start them again:

```bash
./setup.sh compose -- up -d
```

Repeat GPU preparation (normally unnecessary):

```bash
./setup.sh warmup
```

The `compose` command runs Docker Compose only for directories containing this tool's installation metadata. It detects changes to the installation's `compose.yaml` and stops if the file has been modified. For manual changes, use the regular `docker compose` command in the installation directory and keep track of your changes.

## What this changes

See [Architecture and pinned versions](docs/architecture.md) (Japanese). The main changes are:

1. Compatibility settings that treat Vega 11 as the similar gfx900 architecture.
2. Additional gfx900 rocBLAS computation data and a build of the MIGraphX GPU device library.
3. A workaround for the GPU data transfer path that caused errors when reloading models.
4. Input-shape caches provided by the official 3.3.1 implementation, with initial GPU preparation using the default models and sample images.

The Immich server, database, and Valkey use official images. Only the machine learning image and its runtime settings are customized. The old 3.2.0 OCR patches and custom settings have been removed. Model revision `main` (the legacy model exports) is used; the new `v2` exports are outside the tested scope.

## Limitations and updates

- Other GPUs, operating systems, and kernels have not been tested.
- Sample images verify the processing pipeline. They do not guarantee recognition accuracy for real driver's licenses or small text.
- Previously unseen input sizes, such as those needed for long lines of text, may trigger additional GPU compilation.
- GPU video transcoding is not configured.
- Versions are not updated automatically. When developing changes to the same v3.3.1 source, use `install --rebuild` to rebuild the machine learning image, specifying the original directory, project name, and port. Photos, the database, and administrator settings are retained. `--rebuild` only rebuilds the image within the same Immich version; mixing a 3.3.1 ML image into a v3.2.0 installation is rejected. When updating Immich or ROCm, check GPU library compatibility and verify in an isolated environment first.
- Set up photo and database backups separately. See the [Immich backup instructions](https://docs.immich.app/administration/backup-and-restore/).

[Validation results](docs/validation.md) (Japanese) / [Sources and licenses](THIRD_PARTY_NOTICES.md) (Japanese)

This repository turns the hardware investigation and fixes performed by GPT-6 Astra into reusable setup scripts and verification steps. It is not an official Immich, AMD, or Lenovo project.
