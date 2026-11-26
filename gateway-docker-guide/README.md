# Affinidi Agent Gateway — Docker Guide

## About

Agent Gateway is an intercepting proxy that sits between callers and managed agent backends. It applies identity verification, policy enforcement, and observability to every request, from one configuration layer, without changing agent or backend code. It is protocol aware (A2A, MCP, AP2 and more) and is part of Affinidi Trust Fabric.

For what the gateway does and how it works, see the [Agent Gateway documentation](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/) and its [overview](https://docs.affinidi.com/products/affinidi-trust-fabric/agent-gateway/overview/).

## Run it with Docker

| | |
|---|---|
| Gateway version | The version in the `image:` line of your `compose.yaml`. In this guide it is written as `<version>`, for example `1.0.10`. |
| Docker image | `public.ecr.aws/affinidi/agent-gateway:v<version>` |
| Processor types | `amd64` (Intel/AMD x86-64) and `arm64` (Apple Silicon, AWS Graviton) |
| Operating systems | macOS, Linux, Windows (with Docker Desktop) |

This guide explains how to run the Affinidi Agent Gateway with Docker. You can try it on your own computer first, and then run it on a server.

---

## 1. What you need

You need one file: **[`compose.yaml`](compose.yaml)**, in this folder.

You do not need to build source code, run scripts, or download a package. The first start prepares everything automatically.

### What happens on the first start

When you run `docker compose up -d` for the first time, a short setup step (`init`) runs before the gateway starts. It creates these folders **in the same folder as `compose.yaml`**:

```text
my-gateway/
├── compose.yaml          ← the file from this folder
├── .env                  ← optional, you create it (section 4, Step 2)
├── config/               ← created on the first start: configuration files
├── certs/                ← created on the first start: TLS certificate (temporary, self-signed)
├── secrets/              ← created on the first start: secret keys (keys.env)
├── storage/              ← created on the first start: gateway data
└── backup_restore/       ← created on the first start: backups made from the dashboard
```

The setup step does these tasks:

| Task | How |
|---|---|
| Creates three secret keys | Random values, made with `openssl` inside the container. They are saved in `secrets/keys.env`. |
| Creates `config/config.toml` | The gateway program has a built-in command that writes a default configuration file. The setup step runs this command from the same Docker image. |
| Downloads the other configuration files | Downloads the source archive of the same version as the image from the public GitHub repository <https://github.com/affinidi-ai/agent-gateway>. It copies only the default files from the folder `config/examples`, for example `gateway.json`, `rbac.json`, and the agent surface templates. |
| Sets your address | Writes the gateway address (default `http://localhost:8080`) into `config/gateway.json`. |
| Turns on data encryption | Stored data in `storage/` is encrypted with the secret key. |
| Creates a certificate | A temporary self-signed certificate for HTTPS. |

The setup step runs again on every start, but it **never overwrites** existing files. Your configuration, keys, and data are safe.

### Where the data is stored

All files are stored **on your computer**, in the folder where `compose.yaml` is. They are not stored inside the container. `compose.yaml` connects (mounts) each folder into the container:

| Folder on your computer | Path in the container | Access |
|---|---|---|
| `config/` | `/app/config` | Read only |
| `certs/` | `/app/certs` | Read only |
| `secrets/` | `/app/secrets` | Read only |
| `storage/` | `/app/_storage` | Read and write |
| `backup_restore/` | `/app/_backup_restore` | Read and write |

This means:

- You can stop, delete, or update the container. Your data stays in your folder.
- You can read and edit the configuration files in `config/` directly on your computer, without `sudo`.
- To back up the gateway, copy the whole folder (section 7).

### The `.env` file is optional

The setup step does **not** create a `.env` file. Without `.env`, the gateway uses the default settings for a trial on your computer (`http://localhost:8080`).

Create `.env` when you need to change a setting, for example the public address on a server. Copy the example file, which lists every setting with its default value:

```bash
cp .env.example .env
```

Section 4, Step 2 explains all settings.

The secret keys are **not** in `.env`. They are created automatically in `secrets/keys.env`.

---

## 2. Requirements

### 2.1 Prerequisites

Check each item before the first start. If an item is not available, use the workaround in the last column.

| # | Item | Why it is needed | How to check | If it is not available |
|---|---|---|---|---|
| 1 | Docker with Compose v2. macOS or Windows: Docker Desktop. Windows uses the WSL 2 backend. Linux: Docker Engine 24 or later with the Compose plugin. | Runs the gateway | `docker compose version` shows `v2.x` or later | Install Docker Desktop or Docker Engine. The command `docker-compose` (with a hyphen) is the old version and is not supported. |
| 2 | Processor type `amd64` or `arm64` | The image exists only for these two types | `docker info --format "{{.Architecture}}"` shows `x86_64` or `aarch64` | No workaround. Use a different computer. |
| 3 | 1 GiB free memory and 2 GiB free disk space | Gateway and its data | Docker Desktop: **Settings → Resources** | Increase the Docker Desktop memory limit, or free disk space. |
| 4 | Free ports 8080 and 8443 | The gateway opens these ports on your computer | macOS/Linux: `lsof -i :8080 -i :8443` shows nothing. Windows: `netstat -ano \| findstr ":8080 :8443"` shows nothing. | Use other ports (section 3, "Port 8080 or 8443 is already in use"). |
| 5 | Access to `public.ecr.aws` (first start only) | Downloads the Docker image | `docker pull public.ecr.aws/affinidi/agent-gateway:v<version>` | Workaround A in section 2.2 |
| 6 | Access to `github.com` (first start only) | Downloads the default configuration files | macOS/Linux: `curl -I https://github.com`. Windows: `curl.exe -I https://github.com` | Workaround B in section 2.2 |
| 7 | Server only: a DNS name, for example `gateway.example.com` | The public address of the gateway | `nslookup gateway.example.com` shows the server address | Required for a server. Not needed for a trial on your computer. |
| 8 | Server only: a trusted TLS certificate, or a reverse proxy or tunnel that provides HTTPS | Browsers and agents need HTTPS | Section 4, Step 3 | Required for a server. Not needed for a trial on your computer. |
| 9 | Server only: firewall allows port 443 from users and agents | Users and agents must reach the gateway | Ask your network team | Required for a server. |

> **Windows:** Run the commands in this guide in PowerShell. Use `curl.exe`, not `curl`. In Windows PowerShell, `curl` is a different command.

> **Company proxy:** If your network uses an HTTP proxy, set it in Docker Desktop (**Settings → Resources → Proxies**) or in the Docker Engine settings. If downloads still fail, use the workarounds in section 2.2.

### 2.2 Workarounds without internet access

Internet access is needed only on the first start. If the computer cannot reach `public.ecr.aws` or `github.com`, prepare the files on another computer that has internet access, and copy them over.

#### Workaround A — No access to `public.ecr.aws` (Docker image)

In the commands below, replace `<version>` with the version in the `image:` line of `compose.yaml`, for example `1.0.10`.

On a computer **with** internet access:

1. Download the image. Use `linux/amd64` for Intel/AMD and `linux/arm64` for ARM (Apple Silicon, AWS Graviton). Choose the type of the **target** computer.

   ```bash
   docker pull --platform linux/amd64 public.ecr.aws/affinidi/agent-gateway:v<version>
   ```

2. Save the image to a file:

   ```bash
   docker save public.ecr.aws/affinidi/agent-gateway:v<version> -o agent-gateway-image-v<version>.tar
   ```

   If Docker shows a content or platform error, add `--platform linux/amd64` to the `docker save` command. This needs Docker 27 or later.

3. Copy `agent-gateway-image-v<version>.tar` to the target computer.

On the **target** computer:

4. Load the image:

   ```bash
   docker load -i agent-gateway-image-v<version>.tar
   ```

5. Create a file named `.env` next to `compose.yaml` with this line:

   ```bash
   AG_IMAGE=public.ecr.aws/affinidi/agent-gateway:v<version>
   ```

   This is required. `compose.yaml` refers to the image by its unique digest. A loaded image may not have this digest, and Docker then tries to download it again. With `AG_IMAGE`, Docker uses the loaded image.

6. Optional check: compare the image ID on both computers. The two values must be the same.

   ```bash
   docker image inspect --format "{{.Id}}" public.ecr.aws/affinidi/agent-gateway:v<version>
   ```

#### Workaround B — No access to `github.com` (configuration files)

1. On a computer **with** internet access, download this file. You can use a browser or the command below.

   `https://github.com/affinidi-ai/agent-gateway/archive/refs/tags/v<version>.tar.gz`

   Replace `<version>` with the version in the `image:` line of `compose.yaml`, for example `1.0.10`.

   ```bash
   curl -L -o agent-gateway-<version>.tar.gz https://github.com/affinidi-ai/agent-gateway/archive/refs/tags/v<version>.tar.gz
   ```

   On Windows, use `curl.exe` instead of `curl`.

2. Copy the file to the target computer. Put it in the same folder as `compose.yaml`, with exactly this name: `agent-gateway-<version>.tar.gz`.
3. Start the gateway as normal. The setup step finds the file and shows `Using local file agent-gateway-<version>.tar.gz`. It does not connect to GitHub.

You can delete the file after the first start.

#### No internet access at all

Use both workarounds. Before the first start, the folder on the target computer contains:

```text
my-gateway/
├── compose.yaml
├── .env                          ← contains AG_IMAGE=... (workaround A)
└── agent-gateway-<version>.tar.gz    ← configuration files (workaround B)
```

Load the image (workaround A, step 4), then continue with section 3 or section 4. For a server, add your other settings to the same `.env` file.

---

## 3. Try it on your computer

Use this part to test the gateway on your laptop or desktop. The gateway is reachable only from your own computer.

### Step 1 — Create a folder

Create an empty folder in any location and copy `compose.yaml` into it.

| System | Example folder |
|---|---|
| macOS | `~/agent-gateway` |
| Linux | `~/agent-gateway` |
| Windows | `C:\agent-gateway` |

### Step 2 — Start the gateway

Open a terminal (on Windows: PowerShell) in the folder and run:

```bash
docker compose up -d
```

The first start takes 1 to 2 minutes, because Docker downloads the image. Check the status:

```bash
docker compose ps
```

Wait until the `agent-gateway` status shows `healthy`.

### Step 3 — Check the gateway

```bash
curl http://localhost:8080/api/v1/version
```

Expected result: `{"version":"<version>"}`, the version in the `image:` line of `compose.yaml`.

On Windows PowerShell, type `curl.exe` instead of `curl`.

### Step 4 — Open the dashboard

Open this address in your browser: **<http://localhost:8080/dashboard/>**

Register an account. The first account becomes the main administrator.

> **Important:** Use exactly `http://localhost:8080`. Do not use `http://127.0.0.1:8080`, even if Docker Desktop shows this link. Browsers do not allow passkeys (WebAuthn) on an IP address. Passkey login works only with the address in the configuration.

### Port 8080 or 8443 is already in use

Create a file named `.env` in the same folder, **before the first start**:

```bash
AG_HTTP_PORT=18080
AG_HTTPS_PORT=18443
```

Then open `http://localhost:18080/dashboard/`.

Set the ports **before the first start**. On the first start, the setup step writes the address with the HTTP port (for example `http://localhost:18080`) into `config/gateway.json`. If you change `AG_HTTP_PORT` later, the dashboard and passkey login stop working, because the saved address still has the old port.

If you already started the gateway with the old ports, reset the trial (see below) and start again. For a trial this is the simplest fix. To keep your data, edit the address instead (section 6, "Change the address later").

### Reset the trial

To delete everything and start again from the beginning:

```bash
docker compose down
```

Then delete the created folders. Keep `compose.yaml` and `.env`:

```bash
rm -rf config certs secrets storage backup_restore
```

On Linux, add `sudo` in front, because the container user owns `secrets` and `storage`.

---

## 4. Run it on a server

On a server, other people and agents connect to the gateway through a public address, for example `https://gateway.example.com`.

### Step 1 — Prepare the server

1. Create a DNS name for the server, for example `gateway.example.com`.
2. Create a folder in any location, for example `/srv/agent-gateway` or your home folder.
3. Copy `compose.yaml` into the folder.

### Step 2 — Create the settings file (.env)

The `.env` file is not created automatically. Copy the example file in the same folder as `compose.yaml`, **before the first start**, and change the values:

```bash
cp .env.example .env
```

`.env.example` contains the template below (it also has `AG_IMAGE`, see the table):

```bash
# Public address of the gateway. Change this to your DNS name.
PUBLIC_URL=https://gateway.example.com

# Where the ports open on this server. 127.0.0.1 = this server only.
AG_PUBLISH_ADDRESS=127.0.0.1

# Ports on this server.
AG_HTTP_PORT=8080
AG_HTTPS_PORT=8443

# Log level.
RUST_LOG=info
```

You can leave out any line. A missing line uses the default value.

#### All settings

| Setting | Meaning | Default | When it takes effect |
|---|---|---|---|
| `PUBLIC_URL` | The address that browsers and agents use to reach the gateway. **On a server, you must set it to your DNS name.** | `http://localhost:8080` | First start only |
| `AG_PUBLISH_ADDRESS` | The network address where the ports open. `127.0.0.1` = this server only. `0.0.0.0` = all networks. Or a private IP address of the server. This is a network setting only. It must be an IP address. It is not the address you open in the browser. | `127.0.0.1` | Every start |
| `AG_HTTP_PORT` | HTTP port on the server. Change it if 8080 is in use. | `8080` | Every start |
| `AG_HTTPS_PORT` | HTTPS port on the server. Change it if 8443 is in use. Use `443` for option B in Step 3. | `8443` | Every start |
| `RUST_LOG` | Log level: `error`, `warn`, `info`, or `debug` | `info` | Every start |
| `AG_IMAGE` | A different Docker image. Use it for an image loaded from a file (section 2.2, workaround A), or to run another version (section 8, "Choose the gateway version"). | The image in `compose.yaml` | Every start |

#### Rules for `PUBLIC_URL`

- Start with `https://` on a server, for example `https://gateway.example.com`.
- Use the DNS name only. Do not add a path or a `/` at the end.
- Do not add a port on a server. The public address must use the standard HTTPS port 443.
- Set it **before the first start**. On the first start, the setup step writes the address into `config/gateway.json`. After that, changes to `PUBLIC_URL` in `.env` have no effect. To change the address later, see section 6.

#### When you change `.env`

For settings marked "Every start", apply the change with:

```bash
docker compose up -d
```

### Step 3 — Choose how traffic reaches the gateway

Choose one option.

| Option | Use when | Settings in `.env` |
|---|---|---|
| **A. Reverse proxy or load balancer** (for example Nginx, a cloud load balancer, or a tunnel) | You already have one, or you want it to manage the certificate. | `AG_PUBLISH_ADDRESS=127.0.0.1` if the proxy runs on the same server. Use the server's private IP address if the proxy is on another machine. The proxy forwards HTTPS traffic to port `8080`. |
| **B. Direct HTTPS** | You have no proxy. The gateway uses your certificate. | `AG_PUBLISH_ADDRESS=0.0.0.0` and `AG_HTTPS_PORT=443`. Put your certificate in `certs/` (Step 5). Block port 8080 in the firewall. |

For option A, add the IP addresses of the proxy to `config/gateway.json` after the first start, so the gateway logs the real client IP addresses:

```json
"client_ip": {
  "trusted_proxies": ["10.0.1.10"]
}
```

### Step 4 — Start the gateway

```bash
docker compose up -d
docker compose ps
```

Wait until the status shows `healthy`.

### Step 5 — Install your certificate (option B only)

Replace the two files in `certs/`:

| File | Content |
|---|---|
| `cert.pem` | Your certificate with the full chain, PEM format |
| `key.pem` | The private key, PEM format |

Then restart. The setup step sets the correct file owner again:

```bash
docker compose down
docker compose up -d
```

### Step 6 — Check the installation

From your computer:

```bash
curl https://gateway.example.com/api/v1/health
curl https://gateway.example.com/.well-known/did.json
```

The first command returns `{"status":"OK"}`. The DID document must start with `"id":"did:web:gateway.example.com"`.

### Step 7 — Create the first administrator

Open `https://gateway.example.com/dashboard/` and register.

> **Important:** The first account that registers becomes the main administrator. Register immediately after the first start. Until then, allow access only from trusted networks.

---

## 5. Protect the secret keys

The file `secrets/keys.env` contains three keys:

| Key | Purpose |
|---|---|
| `AG_MASTER_KEY` | Encrypts the data in `storage/` |
| `AG_BACKUP_ENCRYPTION_KEY` | Encrypts backups made from the dashboard |
| `AG_IDENTITY_HASH_PEPPER` | Protects identity values that the gateway stores |

- Save a copy of `keys.env` in a secure place, for example a password manager or a secrets vault.
- If you lose `AG_MASTER_KEY`, you cannot read the stored data.
- Do not change the keys after the first start.
- Do not send this file to anyone, including Affinidi support.

---

## 6. Daily operation

| Task | Command |
|---|---|
| Show status | `docker compose ps` |
| Show logs | `docker compose logs -f agent-gateway` |
| Restart | `docker compose restart agent-gateway` |
| Stop | `docker compose down` |
| Start | `docker compose up -d` |

The gateway starts again automatically after a computer restart, unless you stopped it with `docker compose down`.

### Normal warnings

You can ignore these messages on a new installation:

- `At least one channel must be configured` — no agent surfaces exist yet.
- `No DID cache provided` — normal default behavior.
- `did.domain 'localhost' ...` — appears only in a local trial.

### Change the address later

The address is saved in `config/gateway.json`. Edit these values, then restart with `docker compose down` and `docker compose up -d`:

- `did.domain` — host name only, for example `gateway.example.com`
- `webauthn.rp_id` — host name only
- `webauthn.external_origin` — full address, for example `https://gateway.example.com`
- `external_urls` of the listener on port 8080 — add the full address

> Changing the address changes the gateway identity (DID). Agents that already connect to the gateway must use the new address.

---

## 7. Backup and restore

Everything is in your gateway folder: `compose.yaml`, `.env`, configuration, keys, and data.

**Backup:**

1. Run `docker compose down`.
2. Copy the whole folder to a secure place. On Linux, use `sudo` to copy.
3. Run `docker compose up -d`.

**Restore:**

1. Run `docker compose down`.
2. Replace the folder with the copy.
3. Run `docker compose up -d`.

The backup contains the secret keys. Store it securely.

---

## 8. Choose the gateway version and upgrade

### Choose the gateway version

`compose.yaml` runs the version named in its `image:` line. To run a different release, set `AG_IMAGE` in `.env` to that release's image. No other change is needed, because the setup step reads the version from the image and downloads the matching configuration files.

```bash
AG_IMAGE=public.ecr.aws/affinidi/agent-gateway:v<version>
```

- Use an exact version tag, for example `v1.0.10`. There is no `latest` tag. The available versions are listed on <https://gallery.ecr.aws/affinidi/agent-gateway>.
- Set it **before the first start** to begin on that version. To switch later, follow the upgrade steps below.
- Use a version that is not much older or newer than the one in `compose.yaml`. The setup step and the configuration files it creates are checked against that release.
- An `AG_IMAGE` line overrides the image in `compose.yaml`. Remove the line to return to the version in `compose.yaml`.

### Upgrade to a later version

1. Read the release notes of the new version.
2. Make a backup (section 7).
3. Replace `compose.yaml` with the new `compose.yaml` from this folder. Keep `.env` and all other folders.
4. Run:

   ```bash
   docker compose pull
   docker compose up -d
   ```

5. Check the version: `curl http://localhost:8080/api/v1/version`

If `.env` contains an `AG_IMAGE` line (for example, from workaround A in section 2.2), this line overrides `compose.yaml`. Remove the line before the upgrade, or change it to the new image. Without internet access, load the new image first (workaround A), then run only `docker compose up -d`.

The upgrade keeps your existing configuration. If a new version needs configuration changes, the release notes describe them.

To go back, restore the backup and the previous `compose.yaml`.

---

## 9. Troubleshooting

| Problem | Solution |
|---|---|
| `port is already allocated` | Another program uses the port. Set `AG_HTTP_PORT` and `AG_HTTPS_PORT` in `.env`. |
| `init` fails with a download error | The computer cannot reach `github.com`. Use workaround B in section 2.2. |
| `pull access denied`, `timeout`, or `failed to resolve` for `public.ecr.aws` | The computer cannot reach the Docker image registry. Use workaround A in section 2.2. |
| Docker downloads the image again after `docker load` | `AG_IMAGE` is missing in `.env`. See workaround A, step 5. |
| Container restarts again and again | Run `docker compose logs agent-gateway` and look for lines with `ERROR`. |
| Passkey registration fails, or the browser shows a WebAuthn error | Open the dashboard with exactly the address in `PUBLIC_URL`. For a local trial, use `http://localhost:8080`, not `http://127.0.0.1:8080`. Browsers do not allow passkeys on an IP address. |
| DID document shows `localhost` on a server | `PUBLIC_URL` was not set before the first start. See "Change the address later" in section 6. |
| Browser shows a certificate warning on port 8443 | The certificate is self-signed. This is normal for a trial. On a server, use option A or install your certificate (option B). |
| `no matching manifest for linux/...` | The processor is not `amd64` or `arm64`. |

When you contact Affinidi support, send the gateway version and the output of `docker compose logs --tail 300 agent-gateway`. Do not send the `secrets` folder or the private key.

---

## 10. Security checklist for servers

- [ ] `PUBLIC_URL` is your HTTPS address.
- [ ] A trusted certificate is used (on the proxy, or in `certs/`).
- [ ] Port 8080 is not reachable from the internet.
- [ ] Port 9000 is not published (default).
- [ ] The first administrator is registered.
- [ ] `secrets/keys.env` is saved in a secure place.
- [ ] Backups run regularly, and a restore was tested.
- [ ] Only administrators can read the gateway folder.
