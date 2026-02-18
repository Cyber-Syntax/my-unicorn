# Checksum Test Fixtures

This directory contains real-world checksum file samples for testing the hash
encoding detection and normalization logic in `checksum_parser.py`.

## Test Files Overview

| File | Format | Encoding | Algorithm | Purpose |
|------|--------|----------|-----------|---------|
| `heroic_latest-linux.yml` | YAML | Hex | SHA512 | Test hex detection (128 chars) |
| `legcord_latest-linux.yml` | YAML | Base64 | SHA512 | Test base64 detection and conversion |
| `qownnotes_SHA256SUMS.txt` | Traditional | Hex | SHA256 | Test traditional format parsing |
| `siyuan_SHA256SUMS.txt` | Traditional | Hex | SHA256 | Test traditional format parsing |
| `superproductivity_latest-linux.yml` | YAML | Base64 | SHA512 | Test base64 detection and conversion |
| `beekeeper-studio_latest-linux.yml` | YAML | Base64 | SHA512 | Test base64 detection and conversion |
| `affine_latest-linux.yml` | YAML | Base64 | SHA512 | Test base64 detection and conversion |
| `drawio_latest-linux.yml` | YAML | Base64 | SHA512 | Test base64 detection and conversion |
| `joplin_latest-linux.yml` | YAML | Base64 | SHA512 | Test base64 detection and conversion |
| `dangerous_hex.yml` | YAML | Hex | SHA512 | **CRITICAL**: Test hex that looks like base64 |

## Expected Hash Values

### heroic_latest-linux.yml (Hex SHA512)

- **Input**: `3afc23ec03118744c300df152a37bf64593f98cb73159501b6ab23d58e159eef24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f`
- **Expected Output**: Same as input (lowercase)
- **Length**: 128 characters (SHA512 hex)

### legcord_latest-linux.yml (Base64 SHA512)

- **Input**: `JNmYBTG9lqXt/VXmes32pu3bnz/YaKMzfjFVL+0J+S8MSWl7nLmHolmUNLFAubpy1JWTUwEdlPW8UhRNxNiQuw==`
- **Expected Output**: `24d9980531bd96a5edfd55e67acdf6a6eddb9f3fd868a3337e31552fed09f92f0c49697b9cb987a2599434b140b9ba72d4959353011d94f5bc52144dc4d890bb`
- **Length**: 128 characters after conversion (SHA512 hex)

### qownnotes_SHA256SUMS.txt (Traditional Hex SHA256)

- **Input**: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`
- **Expected Output**: Same as input (lowercase)
- **Length**: 64 characters (SHA256 hex)

### siyuan_SHA256SUMS.txt (Traditional Hex SHA256)

- **Input**: `9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08`
- **Expected Output**: Same as input (lowercase)
- **Length**: 64 characters (SHA256 hex)

### superproductivity_latest-linux.yml (Base64 SHA512)

- **Input**: `J7Z4So31dqps06FATBrGKfYENLeM18O5s8tuy6P5qov1ObbY3hrQDinLpEfEEU8gG5I+OdBfUnai+XMhJ6KCuA==`
- **Expected Output**: `27b6784a8df576aa6cd3a1404c1ac629f60434b78cd7c3b9b3cb6ecba3f9aa8bf539b6d8de1ad00e29cba447c4114f201b923e39d05f5276a2f9732127a282b8`
- **Length**: 128 characters after conversion (SHA512 hex)

### beekeeper-studio_latest-linux.yml (Base64 SHA512)

- **Input**: `GNiV+He6lEtOG55E6hp0N3dZslmXk4mi7XuDu1IPyFHv4tFmaEEhSVH7fCKVHSrwubF6TtNDYk2pTIvHweUiEQ==`
- **Expected Output**: `18d895f877ba944b4e1b9e44ea1a74377759b259979389a2ed7b83bb520fc851efe2d1666841214951fb7c22951d2af0b9b17a4ed343624da94c8bc7c1e52211`
- **Length**: 128 characters after conversion (SHA512 hex)

### affine_latest-linux.yml (Base64 SHA512)

- **Input**: `MbXIm2CpRJBmSsawMlcdkJ+SXnIM5C17+9A+h3DhBhye564+1cbJD8hnPMV7JqoxTeC24a3426GZI3EI4YmW+Q==`
- **Expected Output**: `31b5c89b60a94490664ac6b032571d909f925e720ce42d7bfbd03e8770e1061c9ee7ae3ed5c6c90fc8673cc57b26aa314de0b6e1adf8dba199237108e18996f9`
- **Length**: 128 characters after conversion (SHA512 hex)

### drawio_latest-linux.yml (Base64 SHA512)

- **Input**: `SQvi0aMyTviB/ZC7bAlspTzXkxyMp2ejSOuQ40ScCbbJfc5KpKjEh9HQESr8Iu1UUBppLfJjJ395mIminUSxIQ==`
- **Expected Output**: `490be2d1a3324ef881fd90bb6c096ca53cd7931c8ca767a348eb90e3449c09b6c97dce4aa4a8c487d1d0112afc22ed54501a692df263277f799889a29d44b121`
- **Length**: 128 characters after conversion (SHA512 hex)

### joplin_latest-linux.yml (Base64 SHA512)

- **Input**: `b/aYTAy3/VlkBtHvCxgEaHGzzYsK2r35akb+vm5CWLsFmE9Q7Fa4TYjNxtz/dgjGLPfAli3NicBB78NWYacVEg==`
- **Expected Output**: `6ff6984c0cb7fd596406d1ef0b18046871b3cd8b0adabdf96a46febe6e4258bb05984f50ec56b84d88cdc6dcff7608c62cf7c0962dcd89c041efc35661a71512`
- **Length**: 128 characters after conversion (SHA512 hex)

### dangerous_hex.yml (Hex that looks like Base64) - **CRITICAL TEST**

This is the most important test case. These hashes:

1. Are valid hexadecimal (128 chars, only [0-9a-f])
2. Could be mistakenly decoded as base64 (all chars are valid base64)
3. **MUST NOT be decoded as base64**

- **Input**: `deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678deadbeef12345678`
- **Expected Output**: Same as input (lowercase) - **NO base64 decoding**
- **Length**: 128 characters (SHA512 hex)

If this hash is incorrectly decoded as base64, it would produce a completely
different (corrupted) value. The fix ensures hex hashes are detected BEFORE
any base64 decode attempt.

## Testing Strategy

1. **Hex Detection Tests**: Verify `_is_likely_hex()` returns True for heroic, qownnotes, siyuan, dangerous_hex
2. **Base64 Detection Tests**: Verify `_is_likely_base64()` returns True for legcord, appflowy, zen
3. **Normalization Tests**: Verify `_normalize_hash_value()` produces expected outputs for all files
4. **Corruption Prevention**: Verify dangerous_hex hashes are NOT corrupted by base64 decode

## Real-World Context

These fixtures simulate actual checksum files from popular AppImage distributions:

- **Heroic Games Launcher**: Gaming platform that uses pure hex SHA512
- **Legcord**: Discord client that uses base64 SHA512  
- **QOwnNotes**: Note-taking app with traditional SHA256SUMS format
- **SiYuan**: Knowledge management app with traditional SHA256SUMS format
- **AppFlowy**: Notion alternative with YAML base64 checksums
- **Zen Browser**: Privacy browser with YAML base64 checksums
