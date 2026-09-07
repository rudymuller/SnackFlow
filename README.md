## Executáveis

O projeto usa PyInstaller para gerar um executável independente por sistema operacional.

### Windows

No PowerShell, execute:

```powershell
.\build_windows.ps1
```

O resultado será criado em `dist\SnackFlow.exe`.

### Linux

Na máquina Linux, execute:

```bash
chmod +x build_linux.sh
./build_linux.sh
```

O resultado será criado em `dist/SnackFlow`.

O banco SQLite deve ficar em `data/SysDB.db`, dentro da pasta `dist` ao distribuir o aplicativo. A pasta `data` é criada automaticamente pelos scripts de build.
