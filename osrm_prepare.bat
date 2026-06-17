@echo off
setlocal enabledelayedexpansion
echo ============================================================
echo  OSRM - Preparation des donnees France par region
echo  Telecharge, verifie l'integrite, fusionne, puis indexe.
echo ============================================================
echo.

set OSRM_DIR=osrm_data
if not exist %OSRM_DIR% mkdir %OSRM_DIR%

set REGIONS=alsace aquitaine auvergne basse-normandie bourgogne bretagne centre champagne-ardenne corse franche-comte haute-normandie ile-de-france languedoc-roussillon limousin lorraine midi-pyrenees nord-pas-de-calais pays-de-la-loire picardie poitou-charentes provence-alpes-cote-d-azur rhone-alpes

echo [1/4] Telechargement des regions...
echo.
for %%r in (%REGIONS%) do (
    set "FILE=%OSRM_DIR%\%%r-latest.osm.pbf"
    set "NEED=1"
    if exist "!FILE!" (
        for %%A in ("!FILE!") do set "FSIZE=%%~zA"
        if !FSIZE! GEQ 1000000 set "NEED=0"
    )
    if "!NEED!"=="1" (
        if exist "!FILE!" del "!FILE!"
        echo   Telechargement %%r...
        curl -L --fail --retry 5 --retry-delay 5 -o "!FILE!" https://download.geofabrik.de/europe/france/%%r-latest.osm.pbf
    ) else (
        echo   %%r present.
    )
)

echo.
echo [2/4] Verification de l'integrite de chaque fichier ^(lecture complete, peut prendre 1-3 min^)...
echo.
set CORRUPT=0
for %%r in (%REGIONS%) do (
    set "FILE=%OSRM_DIR%\%%r-latest.osm.pbf"
    if not exist "!FILE!" (
        echo   MANQUE : %%r
        set /a CORRUPT+=1
    ) else (
        docker run --rm -v "%cd%\%OSRM_DIR%:/data" stefda/osmium-tool osmium fileinfo -e /data/%%r-latest.osm.pbf >nul 2>&1 || (
            echo   TRONQUE : %%r - supprime, a re-telecharger
            del "!FILE!"
            set /a CORRUPT+=1
        )
    )
    if exist "!FILE!" if !CORRUPT!==0 echo   %%r OK
)
if !CORRUPT! GTR 0 (
    echo.
    echo   !CORRUPT! fichier^(s^) a recuperer. RELANCEZ simplement osrm_prepare.bat :
    echo   il re-telechargera uniquement les fichiers supprimes, puis reprendra.
    pause
    exit /b 1
)
echo.
echo   Tous les fichiers sont complets et valides.
echo.

echo [3/4] Fusion des regions avec osmium-tool...
echo.
docker run --rm -v "%cd%\%OSRM_DIR%:/data" stefda/osmium-tool osmium merge /data/alsace-latest.osm.pbf /data/aquitaine-latest.osm.pbf /data/auvergne-latest.osm.pbf /data/basse-normandie-latest.osm.pbf /data/bourgogne-latest.osm.pbf /data/bretagne-latest.osm.pbf /data/centre-latest.osm.pbf /data/champagne-ardenne-latest.osm.pbf /data/corse-latest.osm.pbf /data/franche-comte-latest.osm.pbf /data/haute-normandie-latest.osm.pbf /data/ile-de-france-latest.osm.pbf /data/languedoc-roussillon-latest.osm.pbf /data/limousin-latest.osm.pbf /data/lorraine-latest.osm.pbf /data/midi-pyrenees-latest.osm.pbf /data/nord-pas-de-calais-latest.osm.pbf /data/pays-de-la-loire-latest.osm.pbf /data/picardie-latest.osm.pbf /data/poitou-charentes-latest.osm.pbf /data/provence-alpes-cote-d-azur-latest.osm.pbf /data/rhone-alpes-latest.osm.pbf -o /data/france-latest.osm.pbf --overwrite
if %errorlevel% neq 0 (
    echo   ERREUR fusion. Relancez le script ^(un fichier est peut-etre encore incomplet^).
    pause
    exit /b 1
)

echo.
echo [4/4] Extraction + Partition + Customisation OSRM...
echo.
echo   Extract...
docker run --rm -t -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/france-latest.osm.pbf
if %errorlevel% neq 0 (
    echo   ERREUR extract. Verifiez la RAM allouee a Docker Desktop ^(12 Go minimum^).
    pause
    exit /b 1
)
echo   Partition...
docker run --rm -t -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/france-latest.osrm
if %errorlevel% neq 0 ( echo   ERREUR partition. & pause & exit /b 1 )
echo   Customize...
docker run --rm -t -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/france-latest.osrm
if %errorlevel% neq 0 ( echo   ERREUR customize. & pause & exit /b 1 )

echo.
echo ============================================================
echo  OSRM PRET ! france-latest.osrm est dans %OSRM_DIR%\
echo  Ensuite : ./osrm_data dans docker-compose puis docker-compose up -d
echo ============================================================
pause
