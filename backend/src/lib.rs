use pyo3::prelude::*;
/// python json module in rust
#[pymodule]
mod rustjson {
    use serde_json::*;
    use pyo3::prelude::*;
    use aws_sdk_secretsmanager::Client;
    use ed25519_dalek::{SigningKey,Signer};
    use ed25519_dalek::pkcs8::DecodePrivateKey;
    use sha2::{Sha256, Digest};
    use std::sync::OnceLock;

    static SIGNING_KEY: OnceLock<SigningKey> = OnceLock::new();
    //gets the private key
    fn get_signing_key() -> &'static SigningKey {
        SIGNING_KEY.get_or_init(|| {
            let rt = tokio::runtime::Builder::new_current_thread()
                .enable_all()
                .build()
                .unwrap();

            rt.block_on(async {
                let config = aws_config::load_from_env().await;
                let client = Client::new(&config);

                let response = client
                    .get_secret_value()
                    .secret_id("ims/private_key")
                    .send()
                    .await
                    .expect("Failed to LOAD the key from AWS");

                let secret_json_str = response
                                            .secret_string()
                                            .expect("El secreto no contiene un string válido");

                let json: Value = serde_json::from_str(&secret_json_str).expect("Failed to parse json");

                let pem = json["private_key"].as_str().expect("Failed to parse JSON value to -> STRING");
                SigningKey::from_pkcs8_pem(pem).expect("Failed to parse the key")
            })
        })
    }


    /// json operation
    #[pyfunction]
    ///BORROWS JSON from bytes as a paremeter
    /// SIGN the JSON and CREATES the hash from it
    /// RETURN the JSON to python as long with the SIGN in raw bytes and HASH from it
    fn data(json: &[u8]) -> PyResult<(Vec<u8>, Vec<u8>)> {
        let signing_key = get_signing_key();
        let signature = signing_key.sign(&json);

        let mut hasher = Sha256::new();
        hasher.update(&json);
        let final_hash = hasher.finalize().to_vec();

        Ok((final_hash, signature.to_bytes().to_vec()))
    }
}
