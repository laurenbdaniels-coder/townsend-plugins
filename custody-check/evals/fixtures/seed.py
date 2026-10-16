"""Copy one eval fixture into the eval's working folder, ready to scan.

    python3 -I seed.py <fixture dir> <dest dir>

- `dotenv*` files become `.env*` (fixtures commit env files under a plain name, as scripts/fixtures does).
- `{{SK}}` and `{{SERVICE_JWT}}` become fresh random key-shaped values, so no key is ever committed. Graders check
  the report never prints a whole key: they match the shape, not the value.
- A `seed-env` file (one `NAME kind` per line, kind `url` or `service-jwt`) becomes `.env` with generated values, so
  the fixture commits names only.
"""
import base64, json, os, secrets, shutil, string, sys

ALNUM = string.ascii_letters + string.digits


def rand(n, alphabet=ALNUM):
    return "".join(secrets.choice(alphabet) for _ in range(n - 3)) + "7Qz"


def b64url(data):
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def jwt(payload):
    return ".".join((b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()),
                     b64url(json.dumps(payload).encode()), rand(43, ALNUM + "_-")))


VALUES = {
    "{{SK}}": "sk-" + rand(39, ALNUM + "_-") + "7",
    "{{SERVICE_JWT}}": jwt({"iss": "supabase", "ref": "abcdefgh", "role": "service_role", "iat": 1, "exp": 2}),
}


ENV_KINDS = {"url": "https://abcdefgh.supabase.co", "service-jwt": VALUES["{{SERVICE_JWT}}"]}


def write_env(dest):
    spec = os.path.join(dest, "seed-env")
    if not os.path.exists(spec):
        return
    with open(spec, encoding="utf-8") as fh:
        pairs = [ln.split() for ln in fh if ln.strip() and not ln.startswith("#")]
    with open(os.path.join(dest, ".env"), "w", encoding="utf-8") as fh:
        fh.writelines("%s=%s\n" % (name, ENV_KINDS[kind]) for name, kind in pairs)
    os.remove(spec)


def main(src, dest):
    shutil.copytree(src, dest)
    write_env(dest)
    for root, _dirs, files in os.walk(dest):
        for name in files:
            path = os.path.join(root, name)
            if name.startswith("dotenv"):
                new = os.path.join(root, ".env" + name[len("dotenv"):])
                os.rename(path, new)
                path = new
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            filled = text
            for k, v in VALUES.items():
                filled = filled.replace(k, v)
            if filled != text:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(filled)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
