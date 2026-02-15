fn main() {
    tonic_build::configure()
        .build_server(true)
        .compile(&["proto/knowledge.proto"], &["proto"])
        .expect("failed to compile protos");
}
