use anyhow::Result;
use async_trait::async_trait;
use reqwest::header::CONTENT_TYPE;
use serde::{Deserialize, Serialize};

use crate::ports::Embedder;

#[derive(Debug, Serialize)]
struct EmbeddingRequest<'a> {
    input: &'a [String],
    model: &'a str,
}

#[derive(Debug, Deserialize)]
struct EmbeddingResponse {
    data: Vec<EmbeddingDatum>,
}

#[derive(Debug, Deserialize)]
struct EmbeddingDatum {
    embedding: Vec<f32>,
}

pub struct OpenAiCompatibleEmbedder {
    client: reqwest::Client,
    base_url: String,
    model_alias: String,
}

impl OpenAiCompatibleEmbedder {
    pub fn new(base_url: String, model_alias: String) -> Self {
        Self {
            client: reqwest::Client::new(),
            base_url,
            model_alias,
        }
    }
}

#[async_trait]
impl Embedder for OpenAiCompatibleEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        if texts.is_empty() {
            return Ok(vec![]);
        }

        let url = format!("{}/embeddings", self.base_url.trim_end_matches('/'));
        let response: EmbeddingResponse = self
            .client
            .post(url)
            .header(CONTENT_TYPE, "application/json")
            .json(&EmbeddingRequest {
                input: texts,
                model: &self.model_alias,
            })
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(response.data.into_iter().map(|d| d.embedding).collect())
    }
}

pub struct MockEmbedder;

#[async_trait]
impl Embedder for MockEmbedder {
    async fn embed_texts(&self, texts: &[String]) -> Result<Vec<Vec<f32>>> {
        Ok(texts
            .iter()
            .map(|text| {
                let mut v = vec![0.0_f32; 3072];
                for (idx, byte) in text.as_bytes().iter().enumerate() {
                    v[idx % 3072] += (*byte as f32) / 255.0;
                }
                v
            })
            .collect())
    }
}
