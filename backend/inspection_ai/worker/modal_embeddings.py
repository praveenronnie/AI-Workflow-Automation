from __future__ import annotations

import logging

import modal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

APP_NAME = "embedding-service"
GPU = "A10"
MODAL_TIMEOUT = 300
BATCH_SIZE = 32
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"

app = modal.App(APP_NAME)

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "sentence-transformers", "torch"
)


@app.cls(
    image=image,
    gpu=GPU,
    timeout=MODAL_TIMEOUT,
    scaledown_window=300,
    secrets=[modal.Secret.from_name("form-automation")],
)
class EmbeddingService:
    @modal.enter()
    def load_model(self):
        from sentence_transformers import SentenceTransformer
        import os

        HF_TOKEN = os.environ["HF_TOKEN"]

        logger.info(f"Loading {EMBEDDING_MODEL} model...")
        self.model = SentenceTransformer(EMBEDDING_MODEL, device="cuda", token=HF_TOKEN)
        logger.info("Model loaded successfully")

    @modal.method()
    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        logger.info(f"Encoding {len(texts)} texts")

        embeddings = self.model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            batch_size=BATCH_SIZE,
        ).astype("float32")

        result = embeddings.tolist()
        logger.info(f"Returned {len(result)} embeddings")
        return result


@app.function()
def test_run(texts: str = "test query,another example"):
    text_list = [text.strip() for text in texts.split(",") if text.strip()]

    if not text_list:
        raise ValueError("At least one text must be provided.")

    logger.info(f"Test run with {len(text_list)} texts")
    service = EmbeddingService()
    embeddings = service.encode_batch.remote(text_list)
    logger.info(
        "Received %d embeddings",
        len(embeddings),
    )
    return embeddings
