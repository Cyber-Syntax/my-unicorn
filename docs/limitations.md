# Limitations

## API requests

Unfortunately, we must use 2 API request for prerelease versions on URL installation.
Catalog installations haven't been this limitation because of the prerelease asset variable
in the catalog config.

NOTE: Catalog apps are optimized to avoid duplicate API calls:

- If catalog specifies prerelease=true, we call fetch_latest_prerelease() directly (1 API call)
- If catalog specifies prerelease=false, we call fetch_latest_release_or_prerelease()
  which tries stable first (/releases/latest), then fallbacks to prerelease only if needed

For URL installs (apps without catalog entries):

- Must use fetch_latest_release_or_prerelease(prefer_prerelease=False) fallback pattern
- This may result in 2 API calls for prerelease-only repos (try stable, then prerelease)
- This is a known limitation due to GitHub API design (/releases/latest only returns stable)

The release_data is cached in UpdateInfo.release_data for reuse in update_single_app()
to avoid redundant API calls within the same operation.
