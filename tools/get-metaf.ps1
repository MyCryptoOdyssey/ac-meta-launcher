# Fetches the metaf converter (JJEII/metaf, GPL-3.0) at a pinned commit and builds it on the .NET 8 SDK.
# metaf is used as a build tool only; its source is not part of this repository.
$ErrorActionPreference = 'Stop'
$commit = '838640f'
$src = Join-Path $PSScriptRoot 'vendor\metaf-src'
if (-not (Test-Path $src)) {
    git clone https://github.com/JJEII/metaf.git $src
}
git -C $src fetch --quiet origin
git -C $src checkout --quiet $commit
dotnet build (Join-Path $PSScriptRoot 'metaf-build\metaf-build.csproj') -c Release -o (Join-Path $PSScriptRoot 'metaf-bin')
& (Join-Path $PSScriptRoot 'metaf-bin\metaf.exe') -version
