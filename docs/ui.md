# UI Documentation

## Installation with Warnings Example

When installing an application that does not provide verification checksums, the user is informed with a warning during the installation process. Below is an example of such an installation using the `my-unicorn` CLI tool:

```bash
my-unicorn install weektodo
Fetching from API:
GitHub Releases      1/1 Retrieved from cache

Downloading:
WeekToDo-2.2.0  108.6 MiB  11.2 MB/s 00:00 [==============================]   100% ✓

Installing:
(1/2) Verifying weektodo ⚠
    not verified (dev did not provide checksums)
(2/2) Installing weektodo ✓


📦 Installation Summary:
--------------------------------------------------
weektodo                  ✅ 2.2.0
                             ⚠️  Not verified - developer did not provide checksums

🎉 Successfully installed 1 app(s)
⚠️  1 app(s) installed with warnings
```
