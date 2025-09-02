from pypdf import PdfReader 
from tqdm import tqdm
import re

class Text_Provider:
    def get_payloads(self):
        '''Returns a list of strings'''
        reader = PdfReader('Taleb Nassim - The Black Swan.pdf') 
        pages = reader.pages[20:] 

        txt = ''.join([page.extract_text() for page in pages])
        sentences = self._extract_sentences(txt)
        filtered_sentences = self._filter_sentences(sentences)
        
        return filtered_sentences
    
    def _extract_sentences(self, text):
        """Extract sentences from text, trying to reconstruct broken lines"""
        # Replace multiple spaces/newlines with single space
        text = re.sub(r'\s+', ' ', text)
        
        # Split into potential sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        return [s.strip() for s in sentences if s.strip()]
    
    def _filter_sentences(self, sentences):
        """Filter out unwanted sentences and return clean content"""
        filtered = []
        
        for sentence in tqdm(sentences):
            # Skip empty sentences
            if not sentence:
                continue
                
            # Skip very short sentences (less than 20 characters)
            if len(sentence) < 20:
                continue
                
            # Skip sentences that are all uppercase (likely headers)
            if sentence.isupper():
                continue
                
            # Skip code-like content
            if any(code_pattern in sentence.lower() for code_pattern in [
                '#define', 'struct', 'sizeof', '#include', 'v4l2_', 
                'user_data', '/* for use', '*/', '//', 'int main',
                'converter trial', 'epub', 'abc amber'
            ]):
                continue
                
            # Skip bibliography/reference entries (names with dates in parentheses)
            if re.search(r'\b[A-Z][a-z]+,\s+[A-Z][a-z]+.*\d{4}\b', sentence):
                continue
            
            # Skip bibliography entries (journal names, publishers, etc.)
            if any(bib_pattern in sentence for bib_pattern in [
                'Oxford University Press', 'Quarterly Journal', 'Cambridge University Press',
                'New York:', 'London:', 'Press.', 'Journal of', 'ed.,', 'Lectures in'
            ]):
                continue
                
            # Skip sentences with excessive numbers/years
            if len(re.findall(r'\b\d{4}\b', sentence)) > 2:
                continue
                
            # Skip sentences that look like page headers/footers
            if re.match(r'^(page|chapter|\d+)\s*\d*$', sentence.lower().strip()):
                continue
                
            # Skip sentences with excessive special characters
            special_char_ratio = sum(1 for c in sentence if not c.isalnum() and c not in ' .,!?;:-\'\"') / len(sentence)
            if special_char_ratio > 0.2:
                continue
                
            # Must contain actual words (not just numbers and symbols)
            words = re.findall(r'\b[a-zA-Z]{3,}\b', sentence)
            if len(words) < 3:  # At least 3 meaningful words
                continue
                
            # Skip sentences that don't end properly (fragmented)
            if not sentence.rstrip().endswith(('.', '!', '?', ':', ';')):
                # Try to find if it continues in next sentence and merge
                continue
                
            # Clean up the sentence
            cleaned = self._clean_sentence(sentence)
            if cleaned:
                filtered.append(cleaned)
        
        return filtered
    
    def _clean_sentence(self, sentence):
        """Clean up formatting issues in a sentence"""
        # Remove excessive whitespace
        sentence = re.sub(r'\s+', ' ', sentence)
        
        # Fix common OCR issues
        sentence = sentence.replace('  ', ' ')
        sentence = sentence.replace(' ,', ',')
        sentence = sentence.replace(' .', '.')
        sentence = sentence.replace(' !', '!')
        sentence = sentence.replace(' ?', '?')
        
        return sentence.strip()