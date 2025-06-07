import logging
from sentence_transformers import SentenceTransformer
from transformers import pipeline

logger = logging.getLogger(__name__)

# Model instances cache
_model_cache = {}

async def get_embedding_model():
    return await _load_model(
        "embedding", 
        lambda: SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
    )

async def get_summarization_model():
    return await _load_model(
        "summarization",
        lambda: pipeline("summarization", model="facebook/bart-large-cnn")
    )

async def _load_model(model_name, loader_func):
    if model_name not in _model_cache:
        logger.info(f"Loading {model_name} model for the first time")
        _model_cache[model_name] = loader_func()
        logger.info(f"{model_name.capitalize()} model loaded successfully")
    return _model_cache[model_name]