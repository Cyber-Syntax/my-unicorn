from importlib.metadata import packages_distributions, version

#TODO: make this work, test
installed = {pkg for pkgs in packages_distributions().values() for pkg in pkgs}
req_str = "\n".join(f"{pkg}=='{version(pkg)}'" for pkg in installed)

with open("requirements.txt", "w") as f:
    f.write(req_str)
