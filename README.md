# PZ3D Schema Migrator

Converts legacy PZ3D model packs broken by the 0.4.1 Assets Manager update into the new `pz3d:assets/1` JSON schema. It parses old `package*.properties` files, transfers transforms, and reorganizes assets into `\common\media\pz3d\assets\`.

## Usage (Executable)

1. Download `PZ3D-Schema-Migrator.exe` from the Releases tab.
2. Launch the application.
3. Click **Browse** next to **Mod Directory** and select the root folder of your old mod (the folder containing `common/` and/or version folders like `42.20.4/`).
4. Click **Browse** next to **Output Dir** and choose an empty destination folder.
5. Click **Start Migration**.
6. Once complete, copy the contents of the output directory over your existing mod folder (or into your `Zomboid/mods/` directory).

## Output Structure

The tool outputs the folder structure required by PZ3D 0.4.1+:

```text
Output_Folder/
├── 42.20.4/            (Copied automatically if present)
│   └── mod.info
└── common/
    └── media/
        └── pz3d/
            └── assets/
                ├── assets.json
                └── [asset-uuid]/
                    ├── model.obj
                    ├── model.mtl
                    └── texture.png
```

## Running from Source

If you prefer running via Python rather than the binary:

```bash
pip install PyQt6
python main.py
```

To compile the `.exe` yourself:

```bash
pip install pyinstaller PyQt6
pyinstaller --noconsole --onefile --name "PZ3D-Schema-Migrator" main.py
```
