fn main() {
    let out_dir = std::env::var("OUT_DIR").expect("OUT_DIR must be set");
    let descriptor_path = format!("{out_dir}/knowledge_descriptor.bin");

    tonic_build::configure()
        .build_server(true)
        .file_descriptor_set_path(&descriptor_path)
        .compile(&["proto/knowledge.proto"], &["proto"])
        .expect("failed to compile protos");
}
