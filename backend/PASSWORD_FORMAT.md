# `users.password` format (PHP CodeIgniter + FastAPI)

## Expected format

Registration and `Login.php` store **one** layer of base64 over AES-256-CBC ciphertext (`my_simple_crypt` in `application/helpers/crud_helper.php`).

For an **8-character** password, the ciphertext is **16 bytes**, so `password` is usually **24 characters** (base64), e.g.  
`sfFCAufYuEpEIXtoWTAcTw==` for plaintext `12345678`.

## Your row (id 7145)

`bENwSkiWQVNCZEppSHRpSkdmQnpidz09` is **32 characters**. That usually means someone applied **base64 twice**.  
But after the **first** decode, the bytes are **not** a valid ASCII inner base64 string (there is a `0x96` byte). So this value is **corrupted or not produced by the normal PHP encrypt path**.

Neither **PHP site login** nor **FastAPI** can verify a password against that blob until the column is fixed.

## Fix in MySQL (set password to `12345678`)

Single-layer hash (same as PHP `my_simple_crypt('12345678')` with default keys):

```sql
UPDATE users
SET password = 'sfFCAufYuEpEIXtoWTAcTw=='
WHERE id = 7145;
```

Then log in with email `demobatch15@avyaya.com` and password `12345678` on both the website and `/auth/login`.

## Generate a hash for any password (local)

From `mock_test/backend`:

```bash
python -c "from app.routers.auth import my_simple_crypt; print(my_simple_crypt('YourPass8'))"
```

Use the printed value in `UPDATE users SET password = '...'`.

## PHP vs “inner only” password (website “invalid password”)

PHP `my_simple_crypt()` saves **`base64_encode(openssl_encrypt(...))`**. With default OpenSSL options, `openssl_encrypt` already returns **base64 text**, so the value in `users.password` is effectively **double base64** (often **~32** characters for an 8-character password).

If you strip it to **inner only** (~24 chars), the **main site login fails** because PHP still compares the **outer** hash.

**Fix inner-only rows** (e.g. after a mistaken normalize). From `mock_test/backend`, after a DB backup:

```bash
python -m scripts.sync_passwords_to_php_outer --dry-run
python -m scripts.sync_passwords_to_php_outer
```

This decrypts each row (inner or outer), then writes back the **exact PHP outer** string. Rows that cannot be decrypted still need admin reset.

**Do not run** `normalize_double_base64_passwords` on production — it is deprecated and breaks PHP.

**FastAPI `/auth/login`:** send **`email` + plain text `password`** (what the user types on the website).  
Do **not** put the 32-character database hash in the JSON `password` field — the server loads `users.password` from MySQL and compares for you.

**Optional DB write after API login:** set environment variable `AUTH_SYNC_PASSWORD_ON_LOGIN=true` only if you want the API to `UPDATE users.password` after a successful login (e.g. to normalize inner-only rows). Default is **false** so PHP remains the only writer of the 32-char hash unless you opt in.
