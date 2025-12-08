# LARS Service binary
# WHY: Bundle the LARS drum separation service for advanced drum processing
# The binary is built separately with Python 3.9/3.10 (required for LarsNet compatibility)
lars_service_dir = project_root / "packaging" / "lars_service"
lars_binary_paths = [
    # Primary: PyInstaller dist output
    lars_service_dir / "dist" / "lars-service",
    # Alternative: resources location
    project_root / "resources" / "lars" / "lars-service",
]

lars_binary = None
for path in lars_binary_paths:
    if path.exists() and path.is_file():
        import os

        if os.access(path, os.X_OK):
            lars_binary = path
            print(f"Found lars-service binary: {path}")
            break
        else:
            # Try to make it executable
            try:
                os.chmod(path, 0o755)
                if os.access(path, os.X_OK):
                    lars_binary = path
                    print(f"Found and made executable: {path}")
                    break
            except Exception as e:
                print(f"Warning: Binary found but cannot make executable: {path} ({e})")

if lars_binary:
    # Bundle to app root for easy discovery by lars_service_client.py
    datas.append((str(lars_binary), "."))
    print(f"Bundling lars-service to app bundle root")
else:
    print(
        "WARNING: lars-service binary not found. LARS drum separation will not be available."
    )
    print("  Build with: cd packaging/lars_service && ./build.sh")
    print("  Searched paths:")
    for path in lars_binary_paths:
        exists = "✓" if path.exists() else "✗"
        print(f"    {exists} {path}")
