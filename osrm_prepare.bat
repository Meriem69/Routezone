@echo off
echo ============================================================
echo  OSRM - Preparation des donnees France par region
echo  Chaque region est telechargee et indexee separement
echo  puis fusionnee. Moins gourmand en RAM.
echo ============================================================
echo.

set OSRM_DIR=osrm_data
if not exist %OSRM_DIR% mkdir %OSRM_DIR%

REM Liste des regions France metropolitaine (Geofabrik)
set REGIONS=alsace aquitaine auvergne basse-normandie bourgogne bretagne centre champagne-ardenne corse franche-comte haute-normandie ile-de-france languedoc-roussillon limousin lorraine midi-pyrenees nord-pas-de-calais pays-de-la-loire picardie poitou-charentes provence-alpes-cote-d-azur rhone-alpes

echo [1/3] Telechargement des regions...
echo.
for %%r in (%REGIONS%) do (
    if not exist %OSRM_DIR%\%%r-latest.osm.pbf (
        echo   Telechargement %%r...
        curl -L -o %OSRM_DIR%\%%r-latest.osm.pbf https://download.geofabrik.de/europe/france/%%r-latest.osm.pbf
    ) else (
        echo   %%r deja telecharge.
    )
)

echo.
echo [2/3] Fusion des regions avec osmium...
echo.

REM Verifier si osmium est disponible via Docker
docker run --rm -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend sh -c "which osmium" >nul 2>&1
if %errorlevel% neq 0 (
    echo   osmium non disponible dans l'image OSRM.
    echo   Fusion manuelle avec osmium-tool...
    docker run --rm -v "%cd%\%OSRM_DIR%:/data" stefda/osmium-tool merge /data/alsace-latest.osm.pbf /data/aquitaine-latest.osm.pbf /data/auvergne-latest.osm.pbf /data/basse-normandie-latest.osm.pbf /data/bourgogne-latest.osm.pbf /data/bretagne-latest.osm.pbf /data/centre-latest.osm.pbf /data/champagne-ardenne-latest.osm.pbf /data/corse-latest.osm.pbf /data/franche-comte-latest.osm.pbf /data/haute-normandie-latest.osm.pbf /data/ile-de-france-latest.osm.pbf /data/languedoc-roussillon-latest.osm.pbf /data/limousin-latest.osm.pbf /data/lorraine-latest.osm.pbf /data/midi-pyrenees-latest.osm.pbf /data/nord-pas-de-calais-latest.osm.pbf /data/pays-de-la-loire-latest.osm.pbf /data/picardie-latest.osm.pbf /data/poitou-charentes-latest.osm.pbf /data/provence-alpes-cote-d-azur-latest.osm.pbf /data/rhone-alpes-latest.osm.pbf -o /data/france-latest.osm.pbf --overwrite
) else (
    docker run --rm -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osmium merge /data/alsace-latest.osm.pbf /data/aquitaine-latest.osm.pbf /data/auvergne-latest.osm.pbf /data/basse-normandie-latest.osm.pbf /data/bourgogne-latest.osm.pbf /data/bretagne-latest.osm.pbf /data/centre-latest.osm.pbf /data/champagne-ardenne-latest.osm.pbf /data/corse-latest.osm.pbf /data/franche-comte-latest.osm.pbf /data/haute-normandie-latest.osm.pbf /data/ile-de-france-latest.osm.pbf /data/languedoc-roussillon-latest.osm.pbf /data/limousin-latest.osm.pbf /data/lorraine-latest.osm.pbf /data/midi-pyrenees-latest.osm.pbf /data/nord-pas-de-calais-latest.osm.pbf /data/pays-de-la-loire-latest.osm.pbf /data/picardie-latest.osm.pbf /data/poitou-charentes-latest.osm.pbf /data/provence-alpes-cote-d-azur-latest.osm.pbf /data/rhone-alpes-latest.osm.pbf -o /data/france-latest.osm.pbf --overwrite
)

echo.
echo [3/3] Extraction + Partition + Customisation OSRM...
echo.

echo   Extract...
docker run --rm -t -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/france-latest.osm.pbf
if %errorlevel% neq 0 (
    echo   ERREUR extract. Verifiez la RAM Docker (12 Go minimum).
    pause
    exit /b 1
)

echo   Partition...
docker run --rm -t -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/france-latest.osrm
if %errorlevel% neq 0 (
    echo   ERREUR partition.
    pause
    exit /b 1
)

echo   Customize...
docker run --rm -t -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/france-latest.osrm
if %errorlevel% neq 0 (
    echo   ERREUR customize.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  OSRM PRET !
echo  Pour lancer le serveur :
echo    docker run -t -p 5000:5000 -v "%cd%\%OSRM_DIR%:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/france-latest.osrm
echo ============================================================
pause
