# TORC repository seed

This package seeds the empty private repository `mdn87/torc` as a separate Lugos subproject at:

```text
C:\Users\Matt\Desktop\MyDocs\lugos\torc
```

The seed is intentionally docs-first. It defines the full TORC Plane boundary, but the included Codex prompt implements only the first falsifiable vertical slice.

## Preferred installation

From PowerShell in the extracted package directory:

```powershell
.\install-torc-seed.ps1
```

The script:

1. Clones `https://github.com/mdn87/torc.git` into the Lugos root if needed.
2. Refuses to overwrite a dirty or already populated repository.
3. Copies the seed files into the cloned repository.
4. Does not commit, push, or modify the parent Lugos repository.

Then open Codex in the new `torc` repository and paste:

```text
docs/prompts/CODEX_BOOTSTRAP_PROMPT.md
```

## Manual installation

Clone the empty repository, then copy everything under this package's `repo/` directory into it:

```powershell
Set-Location C:\Users\Matt\Desktop\MyDocs\lugos
git clone https://github.com/mdn87/torc.git torc
Copy-Item -Recurse -Force <extracted-package>\repo\* .\torc\
```

PowerShell wildcard copying can omit dotfiles in some workflows. Confirm that `.gitignore`, `.gitattributes`, and `.editorconfig` arrived.

## Add TORC to the Lugos parent after the first TORC commit is pushed

From the Lugos parent repository:

```powershell
Set-Location C:\Users\Matt\Desktop\MyDocs\lugos
git submodule add -f https://github.com/mdn87/torc.git torc
git add .gitmodules torc
git commit -m "Add TORC lineage control plane submodule"
git push
```

Do this only after the TORC repository has at least one pushed commit. An empty remote cannot supply a usable submodule commit.
