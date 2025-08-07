@echo off
for /r %%f in (*.py,*.html) do (
    echo --- Contenu de %%f ---
    type "%%f"
    echo.
    echo.
)