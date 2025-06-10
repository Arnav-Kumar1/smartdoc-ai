from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import List, Dict, Any, Optional, Tuple
import os
import time
import nltk
from nltk.tokenize import sent_tokenize
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Download NLTK resources if needed
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class HierarchicalSummarizer:
    """
    A hierarchical map-reduce summarizer for extremely large documents.
    Uses intelligent chunking and a two-phase summarization approach to minimize API calls.
    """
    
    def __init__(
        self,
        model_name: str = "gemini-1.5-flash-latest",
        temperature: float = 0.1,
        max_tokens_per_chunk: int = 4000,
        chunk_overlap: int = 400,
        max_retries: int = 3,
        retry_delay: int = 2,
        api_key: Optional[str] = None # MODIFIED: api_key is now a required parameter
    ):
        """
        Initialize the hierarchical summarizer.
        
        Args:
            model_name: The specific Gemini model to use
            temperature: Temperature setting for generation (lower = more deterministic)
            max_tokens_per_chunk: Maximum tokens per chunk for processing
            chunk_overlap: Number of tokens to overlap between chunks
            max_retries: Maximum number of retries for failed API calls
            retry_delay: Delay between retries in seconds
            api_key: Optional API key (if not provided, will use environment variables)
        """
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens_per_chunk = max_tokens_per_chunk
        self.chunk_overlap = chunk_overlap
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # MODIFIED: Ensure API key is provided and use it directly
        if not api_key:
            raise ValueError("Gemini API key must be provided for HierarchicalSummarizer.")
        
        self.llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=temperature
        )
        
        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=max_tokens_per_chunk,
            chunk_overlap=chunk_overlap,
            length_function=self._count_tokens,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
    
    def _count_tokens(self, text: str) -> int:
        """
        Count the number of tokens in a text string.
        
        Args:
            text: The text to count tokens for
            
        Returns:
            The number of tokens
        """
        # Approximate token count for Gemini (roughly 4 chars per token)
        return len(text) // 4
    
    def _split_into_semantic_chunks(self, text: str) -> List[Tuple[str, int]]:
        """
        Split text into semantically meaningful chunks, preserving sentence boundaries.
        
        Args:
            text: The text to split
            
        Returns:
            List of (chunk, position) tuples where position is the chunk's position in the document
        """
        # First, get raw chunks from the text splitter
        raw_chunks = self.text_splitter.split_text(text)
        
        # Process chunks to ensure they don't break sentences
        processed_chunks = []
        position = 0
        
        for i, chunk in enumerate(raw_chunks):
            # If this is not the first chunk and it starts mid-sentence, 
            # find the first sentence boundary
            if i > 0 and not chunk.startswith((".", "!", "?", "\n")):
                sentences = sent_tokenize(chunk)
                if len(sentences) > 1:
                    # Adjust the chunk to start at a sentence boundary
                    chunk = " ".join(sentences)
            
            processed_chunks.append((chunk, position))
            position += 1
        
        logger.info(f"Split document into {len(processed_chunks)} semantic chunks")
        return processed_chunks
    
    def _create_chunk_batches(self, chunks: List[Tuple[str, int]], batch_size: int = 8) -> List[List[Tuple[str, int]]]:
        """
        Group chunks into batches for more efficient processing.
        
        Args:
            chunks: List of (chunk, position) tuples
            batch_size: Maximum number of chunks per batch
            
        Returns:
            List of batches, where each batch is a list of (chunk, position) tuples
        """
        # For very large documents, we want to create strategic batches
        # that capture different parts of the document
        
        if len(chunks) <= batch_size:
            return [chunks]
        
        # Always include first and last chunks in their respective batches
        first_chunk = chunks[0]
        last_chunk = chunks[-1]
        middle_chunks = chunks[1:-1]
        
        # Calculate optimal number of batches based on document size
        total_chunks = len(chunks)
        
        if total_chunks > 1500:  # Very large document (like Harry Potter series)
            num_batches = min(7, (len(middle_chunks) + batch_size - 2) // (batch_size - 1))
        elif total_chunks > 500:  # Large document
            num_batches = min(5, (len(middle_chunks) + batch_size - 2) // (batch_size - 1))
        else:  # Medium document
            num_batches = min(3, (len(middle_chunks) + batch_size - 2) // (batch_size - 1))
        
        logger.info(f"Creating {num_batches} batches for {total_chunks} total chunks")
        
        # Create batches with evenly distributed chunks
        batches = []
        for i in range(num_batches):
            batch = []
            
            # Add first chunk to first batch
            if i == 0:
                batch.append(first_chunk)
            
            # Calculate which middle chunks go in this batch
            start_idx = i * len(middle_chunks) // num_batches
            end_idx = (i + 1) * len(middle_chunks) // num_batches
            
            # Add middle chunks for this batch
            batch.extend(middle_chunks[start_idx:end_idx])
            
            # Add last chunk to last batch
            if i == num_batches - 1:
                batch.append(last_chunk)
            
            batches.append(batch)
        
        return batches
    
    def _call_llm_with_retry(self, prompt: str) -> str:
        """
        Call the LLM with retry logic for failed API calls.
        
        Args:
            prompt: The prompt to send to the LLM
            
        Returns:
            The LLM's response
            
        Raises:
            Exception: If all retries fail
        """
        for attempt in range(self.max_retries):
            try:
                response = self.llm.invoke(prompt)
                return response.content
            except Exception as e:
                logger.warning(f"API call failed (attempt {attempt+1}/{self.max_retries}): {str(e)}")
                if attempt < self.max_retries - 1:
                    # Exponential backoff
                    sleep_time = self.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"All {self.max_retries} attempts failed")
                    raise
    
    def _map_phase(self, batches: List[List[Tuple[str, int]]]) -> List[str]:
        """
        Map phase: Summarize each batch of chunks.
        
        Args:
            batches: List of batches, where each batch is a list of (chunk, position) tuples
            
        Returns:
            List of summaries, one per batch
        """
        batch_summaries = []
        
        for i, batch in enumerate(batches):
            logger.info(f"Processing batch {i+1}/{len(batches)}")
            
            # Prepare the content with section markers
            combined_text = ""
            for j, (chunk, position) in enumerate(batch):
                # Determine section name based on position in the document
                if position == 0:
                    section_name = "Beginning Section"
                elif position == batches[-1][-1][1]:  # Last chunk's position
                    section_name = "Ending Section"
                else:
                    # Calculate approximate position in document
                    relative_position = position / batches[-1][-1][1]
                    section_name = f"Section {position} (approx. {int(relative_position * 100)}% through document)"
                
                combined_text += f"\n\n--- {section_name} ---\n{chunk}\n"
            
            # Create a prompt for this batch
            prompt = f"""You are summarizing section {i+1} of {len(batches)} of a document.
            I've provided key excerpts from this section of the document.
            
            Create a detailed summary of this section focusing on the main points, key information, and important details.
            Maintain the original tone and purpose of the content.
            Preserve important narrative elements, character development, and key plot points if this is a narrative text.
            
            If this is the first section, try to identify:
            1. What type of document this is (e.g., research paper, novel, technical manual, etc.)
            2. What appears to be the purpose of this document
            3. What problem or question this document seems to address
            4. do not start the summarization with " in first section" or anything similar.
            
            Document excerpts:
            {combined_text}
            
            SECTION {i+1} SUMMARY:"""
            
            # Call the LLM with retry logic
            summary = self._call_llm_with_retry(prompt)
            batch_summaries.append(summary)
        
        return batch_summaries
    
    def _reduce_phase(self, batch_summaries: List[str]) -> str:
        """
        Reduce phase: Combine all batch summaries into a final summary.
        
        Args:
            batch_summaries: List of summaries, one per batch
            
        Returns:
            The final combined summary
        """
        if len(batch_summaries) == 1:
            return batch_summaries[0]
        
        # Combine all summaries with section markers
        combined_summaries = "\n\n".join([f"Section {i+1}:\n{summary}" for i, summary in enumerate(batch_summaries)])
        
        # Create a prompt for the final summary
        final_prompt = f"""I have summaries of different sections of a document that has {len(batch_summaries)} sections.
        Combine these summaries into one coherent, comprehensive summary.
        
        Your final summary MUST begin with a section that answers the following questions:
        1. What type of document is this? (e.g., research paper, novel, technical manual, etc.)
        2. What was the purpose of creating this document?
        3. What problem or question does this document aim to address or solve?
        4. Do not literally have the above 3 questions in the summary. just answer them cohesively
        
        After answering these questions, provide the comprehensive summary of the document content.
        
        Ensure the final summary flows naturally and captures the key information from all sections.
        Maintain the original tone and purpose of the content.
        Preserve important narrative arcs, character development, and key plot points if this is a narrative text.
        
        {combined_summaries}
        
        FINAL COMPREHENSIVE SUMMARY:"""
        
        # Call the LLM with retry logic
        logger.info("Generating final combined summary...")
        final_summary = self._call_llm_with_retry(final_prompt)
        
        return final_summary
    
    def summarize(self, text: str) -> Dict[str, Any]:
        """
        Summarize a document using the hierarchical map-reduce approach.
        
        Args:
            text: The document text to summarize
            
        Returns:
            A dictionary containing the summary and metadata
        """
        logger.info("Starting hierarchical summarization process")
        
        # Step 1: Split the document into semantic chunks
        chunks = self._split_into_semantic_chunks(text)
        
        # Step 2: Create batches of chunks
        batches = self._create_chunk_batches(chunks)
        
        # Step 3: Map phase - summarize each batch
        logger.info(f"Starting map phase with {len(batches)} batches")
        batch_summaries = self._map_phase(batches)
        
        # Step 4: Reduce phase - combine all summaries
        logger.info("Starting reduce phase")
        final_summary = self._reduce_phase(batch_summaries)
        
        logger.info("Summarization complete")
        
        return {
            "summary": final_summary,
            "sections_used": len(chunks),
            "batches_used": len(batches),
            "api_calls": len(batches) + (1 if len(batches) > 1 else 0)  # Map calls + reduce call
        }