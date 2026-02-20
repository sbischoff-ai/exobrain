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

    # Assistant backend (Python + uv)
    python312
    uv

    # Assistant frontend (Svelte/Vite)
    nodejs_22

    # Knowledge interface (Rust)
    rustc
    cargo
    pkg-config
    openssl
    protobuf

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
    export LD_LIBRARY_PATH=${libPath}:$LD_LIBRARY_PATH

    echo "Exobrain development shell ready"
    echo "- Kubernetes: kubectl, helm, k3d"
    echo "- Backend: python, uv"
    echo "- Frontend: node"
    echo "- Rust: cargo"
    echo "- Databases: psql, cypher-shell, curl/http"
  '';
}
