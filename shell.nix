{ pkgs ? import <nixpkgs> {} }:

let
  libPath = pkgs.lib.makeLibraryPath [
    pkgs.postgresql_16
  ];
in
pkgs.mkShell {
  packages = with pkgs; [
    # Core tooling
    docker-compose
    kubectl
    kubernetes-helm
    k3d
    mprocs

    # Assistant backend (Python + uv)
    python312
    uv

    # Assistant frontend (Svelte/Vite)
    nodejs_22
    playwright-driver
    playwright-driver.browsers

    # Knowledge interface (Rust)
    rustc
    cargo
    pkg-config
    openssl
    protobuf
    grpcui

    # Data store CLIs
    postgresql_16 # psql
    neo4j         # cypher-shell (Memgraph-compatible Bolt workflow)
    curl          # Qdrant REST API
    httpie        # Friendly HTTP CLI for Qdrant
    jq
    reshape       # migrations etc.
    rainfrog      # DB TUI client
  ];

  shellHook = ''
    export UV_PYTHON="${pkgs.python312}/bin/python3"
    export PLAYWRIGHT_BROWSERS_PATH="${pkgs.playwright-driver.browsers}"
    export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
    export LD_LIBRARY_PATH=${libPath}:$LD_LIBRARY_PATH
    if [ -f .env.secrets ]; then
      echo "Loading environment from .env.secrets"
      set -a
      source .env.secrets
      set +a
    fi

    echo "Exobrain development shell ready"
    echo "- Kubernetes: kubectl, helm, k3d"
    echo "- Process orchestration: mprocs"
    echo "- Backend: python, uv"
    echo "- Frontend: node"
    echo "- E2E: playwright (nix-provided browsers)"
    echo "- Rust: cargo"
    echo "- Databases: psql, cypher-shell, curl/http"
  '';
}
