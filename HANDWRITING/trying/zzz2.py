import cv2
import re
import numpy as np
from textblob import TextBlob
from difflib import SequenceMatcher
import pyttsx3
import os
import time

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Add fallback mechanism for PaddleOCR
try:
    from paddleocr import PaddleOCR
    paddle_available = True
    print("PaddleOCR is available and will be used.")
except ImportError:
    paddle_available = False
    print("PaddleOCR is not available. Using pytesseract as fallback.")
    try:
        import pytesseract
        if os.name == 'nt':  # Windows
            pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
            print("Using Tesseract OCR as fallback.")
    except ImportError:
        print("Error: Neither PaddleOCR nor pytesseract is available.")
        print("Please install at least one of them:")
        print("pip install pytesseract")
        print("You also need to install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki")
        exit(1)

# Load common English words for validation and correction
def load_common_english_words():
    """Load a more comprehensive list of common English words."""
    try:
        # Try to load from nltk if available
        import nltk
        from nltk.corpus import words as nltk_words
        try:
            nltk.data.find('corpora/words')
        except LookupError:
            nltk.download('words')
        return set(word.lower() for word in nltk_words.words())
    except ImportError:
        # Fall back to a larger built-in list
        word_list = [
            "the", "and", "a", "to", "in", "is", "you", "that", "it", "he", "was", "for", "on", 
            "are", "as", "with", "his", "they", "at", "be", "this", "have", "from", "or", "one", 
            "had", "by", "word", "but", "not", "what", "all", "were", "we", "when", "your", "can", 
            "said", "there", "use", "an", "each", "which", "she", "do", "how", "their", "if", 
            "will", "up", "other", "about", "out", "many", "then", "them", "these", "so", "some", 
            "her", "would", "make", "like", "him", "into", "time", "has", "look", "two", "more", 
            "write", "go", "see", "number", "no", "way", "could", "people", "my", "than", "first", 
            "water", "been", "call", "who", "oil", "its", "now", "find", "long", "down", "day", 
            "did", "get", "come", "made", "may", "part", "over", "new", "sound", "take", "only",
            "little", "work", "know", "place", "year", "live", "me", "back", "give", "most", 
            "very", "after", "thing", "our", "just", "name", "good", "sentence", "man", "think",
            "say", "great", "where", "help", "through", "much", "before", "line", "right", "too",
            "mean", "old", "any", "same", "tell", "boy", "follow", "came", "want", "show", "also",
            "around", "form", "three", "small", "set", "put", "end", "does", "another", "well",
            "large", "must", "big", "even", "such", "because", "turn", "here", "why", "ask",
            "went", "men", "read", "need", "land", "different", "home", "us", "move", "try", "kind",
            "hand", "picture", "again", "change", "off", "play", "spell", "air", "away", "animal",
            "house", "point", "page", "letter", "mother", "answer", "found", "study", "still", "learn",
            "should", "america", "world", "high", "every", "near", "add", "food", "between", "own",
            "below", "country", "plant", "last", "school", "father", "keep", "tree", "never", "start",
            "city", "earth", "eye", "light", "thought", "head", "under", "story", "saw", "left",
            "don't", "few", "while", "along", "might", "close", "something", "seem", "next", "hard",
            "open", "example", "begin", "life", "always", "those", "both", "paper", "together", "got",
            "group", "often", "run", "important", "until", "children", "side", "feet", "car", "mile",
            "night", "walk", "white", "sea", "began", "grow", "took", "river", "four", "carry", "state",
            "once", "book", "hear", "stop", "without", "second", "late", "miss", "idea", "enough",
            "eat", "face", "watch", "far", "indian", "real", "almost", "let", "above", "girl",
            "sometimes", "mountain", "cut", "young", "talk", "soon", "list", "song", "being", "leave",
            "family", "it's"
        ]
        
        # Add more context-specific words relevant to your domain
        domain_words = [
            "read", "text", "handwriting", "paragraph", "sentence", "word", "character",
            "page", "document", "line", "script", "note", "message", "letter", "writing",
            "recognition", "camera", "capture", "scan", "image", "process", "detect"
        ]
        
        return set(word_list + domain_words)

# Enhanced dictionary of common handwriting OCR errors and their corrections
handwriting_corrections = {
    "cl": "d",
    "rn": "m",
    "vv": "w",
    "li": "h",
    "lj": "y",
    "0": "o",
    "l": "i",
    "c]": "d",
    "]": "i",
    "[": "i",
    ",": ".",
    "!": "i",
    "|": "l",
    "i.": "i",
    "i,": "i",
    "l.": "i",
    "l,": "i",
    "1": "l",
    "c1": "d",
    "ri": "n",
    "rri": "m",
    "r n": "m",
    "nn": "m",
    "in": "m",
    "rni": "mi",
    "fi": "h",
    "ii": "u",
    "hc": "he",
    "f+": "ft",
    "f(": "ft",
    "5": "s",
    "e0": "eo",
    "o0": "oo",
    "ao": "co",
    "f1": "fl",
    "l1": "ll",
    "ll": "ll",
    "t1": "tl",
    "t,": "t.",
    "lho": "the",
    "fhe": "the",
    "1s": "is",
    "j": "i",
    "bv": "by"
}

common_english_words = load_common_english_words()

# New function to detect lighting conditions and adjust preprocessing
def analyze_lighting(image):
    """Analyze image lighting conditions to select optimal preprocessing."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    
    # Calculate brightness
    brightness = np.mean(gray)
    
    # Calculate contrast
    contrast = np.std(gray)
    
    # Calculate histogram
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
    hist = hist.flatten() / (gray.shape[0] * gray.shape[1])
    
    # Assess lighting conditions
    lighting_conditions = {
        "brightness": brightness,
        "contrast": contrast,
        "dark_pixels": np.sum(hist[:50]),
        "light_pixels": np.sum(hist[200:]),
        "mid_pixels": np.sum(hist[50:200])
    }
    
    return lighting_conditions

def preprocess_image_for_handwriting(image, lighting_info=None):
    """Apply preprocessing techniques optimized for handwriting OCR based on lighting conditions."""
    # Create a copy of the image
    img = image.copy()
    
    # Convert to grayscale if not already
    if len(img.shape) == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()
    
    # Analyze lighting if not provided
    if lighting_info is None:
        lighting_info = analyze_lighting(img)
    
    # Create multiple variants of preprocessing
    variants = {}
    
    # 1. Basic grayscale
    variants["grayscale"] = gray
    
    # 2. Adaptive thresholding with parameters based on lighting
    block_size = 11
    if lighting_info["contrast"] < 40:
        block_size = 15  # Larger block size for low contrast
    c_value = 5 if lighting_info["brightness"] > 150 else 2
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                                  cv2.THRESH_BINARY, block_size, c_value)
    variants["adaptive_threshold"] = thresh
    
    # 3. Otsu's thresholding
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["otsu"] = otsu
    
    # 4. Contrast enhancement with CLAHE based on lighting
    clahe = cv2.createCLAHE(clipLimit=3.0 if lighting_info["contrast"] < 40 else 2.0, 
                           tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    variants["enhanced"] = enhanced
    
    # 5. Custom thresholding based on lighting
    if lighting_info["brightness"] < 120:
        # Low light - use lower threshold
        _, custom_thresh = cv2.threshold(enhanced, 110, 255, cv2.THRESH_BINARY)
    elif lighting_info["brightness"] > 180:
        # Bright light - use higher threshold
        _, custom_thresh = cv2.threshold(enhanced, 150, 255, cv2.THRESH_BINARY)
    else:
        # Normal light - use Otsu
        _, custom_thresh = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["custom_threshold"] = custom_thresh
    
    # 6. Denoising for cleaner image
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)
    variants["denoised"] = denoised
    
    # 7. Edge enhancement for better character definition
    edges = cv2.Canny(gray, 50, 150)
    dilated_edges = cv2.dilate(edges, np.ones((2, 2), np.uint8), iterations=1)
    variants["edges"] = dilated_edges
    
    # 8. Bilateral filter with adaptive parameters
    bilateral_d = 9 if lighting_info["contrast"] < 40 else 7
    bilateral = cv2.bilateralFilter(gray, bilateral_d, 75, 75)
    _, bilateral_thresh = cv2.threshold(bilateral, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    variants["bilateral"] = bilateral_thresh
    
    # 9. Smart binarization for handwriting - modified Sauvola method
    # Approximate Sauvola's method with OpenCV
    mean = cv2.GaussianBlur(gray, (5, 5), 0)
    mean_sq = cv2.GaussianBlur(gray * gray, (5, 5), 0)
    variance = mean_sq - mean * mean
    std_dev = np.sqrt(variance + 1e-10)
    
    # Threshold formula: T = mean * (1 + k * ((std_dev / R) - 1))
    k = 0.2
    R = 128
    threshold = mean * (1.0 + k * ((std_dev / R) - 1.0))
    sauvola = np.zeros_like(gray)
    sauvola[gray > threshold] = 255
    variants["sauvola"] = sauvola
    
    # 10. Shadow correction for uneven lighting
    if lighting_info["contrast"] > 60:  # Only if high contrast suggests shadows
        # Create a background model by morphological operations
        kernel = np.ones((15, 15), np.uint8)
        bg_model = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        # Normalize the image
        shadow_corrected = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)
        variants["shadow_corrected"] = shadow_corrected
    
    return variants

def extract_text_from_all_variants(image_variants):
    """Extract text from all image variants using multiple OCR engines with optimized parameters."""
    results = []
    
    # Import OCR libraries here to avoid issues if they're not installed
    try:
        import pytesseract
        tesseract_available = True
    except ImportError:
        tesseract_available = False
        print("Warning: pytesseract not available. Install it for better OCR results.")
    
    try:
        import easyocr
        easyocr_available = True
        reader = easyocr.Reader(['en'])
    except ImportError:
        easyocr_available = False
        print("Warning: easyocr not available. Install it for better OCR results.")
    
    # For each preprocessing variant
    for variant_name, img in image_variants.items():
        # Try Tesseract OCR with multiple PSM modes
        if tesseract_available:
            # PSM modes to try (optimized for handwriting)
            psm_modes = [6, 8, 7, 4]  # Single line, word, line, single column
            
            for psm in psm_modes:
                try:
                    # Custom configuration for handwriting
                    config = f'--psm {psm} --oem 1 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!?-\'" -c textord_old_xheight=0'
                    
                    # Add language model config for handwriting if PSM is for multi-line text
                    if psm in [4, 3]:
                        config += ' -c language_model_penalty_non_freq_dict_word=0.8'
                    
                    tesseract_text = pytesseract.image_to_string(img, config=config)
                    tesseract_text = tesseract_text.strip()
                    
                    if tesseract_text:
                        # Calculate confidence based on character recognition confidence
                        char_confidences = []
                        try:
                            char_data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT)
                            for conf in char_data['conf']:
                                if conf != -1:  # -1 means no confidence available
                                    char_confidences.append(conf / 100.0)
                        except:
                            pass
                        
                        confidence = 0.5  # Default
                        if char_confidences:
                            confidence = 0.5  # Default
                        if char_confidences:
                            confidence = sum(char_confidences) / len(char_confidences)
                        
                        results.append({
                            'text': tesseract_text,
                            'method': f'tesseract_{variant_name}_psm{psm}',
                            'confidence': confidence
                        })
                except Exception as e:
                    print(f"Tesseract error on {variant_name} with PSM {psm}: {e}")
        
        # Try EasyOCR with different settings for handwriting
        if easyocr_available:
            try:
                # EasyOCR works better with original grayscale, enhanced, or denoised images
                if variant_name in ["grayscale", "enhanced", "denoised", "sauvola"]:
                    # Use paragraph detection for multi-line text
                    easyocr_result = reader.readtext(img, paragraph=True, detail=1)
                    if easyocr_result:
                        easyocr_text = " ".join([item[1] for item in easyocr_result])
                        avg_confidence = sum([item[2] for item in easyocr_result]) / len(easyocr_result)
                        results.append({
                            'text': easyocr_text,
                            'method': f'easyocr_{variant_name}_paragraph',
                            'confidence': avg_confidence
                        })
                    
                    # Also try without paragraph detection for comparison
                    easyocr_result = reader.readtext(img, paragraph=False, detail=1)
                    if easyocr_result:
                        easyocr_text = " ".join([item[1] for item in easyocr_result])
                        avg_confidence = sum([item[2] for item in easyocr_result]) / len(easyocr_result)
                        results.append({
                            'text': easyocr_text,
                            'method': f'easyocr_{variant_name}_individual',
                            'confidence': avg_confidence
                        })
            except Exception as e:
                print(f"EasyOCR error on {variant_name}: {e}")
    
    # Try to use any other available OCR libraries if installed
    if paddle_available:
        for variant_name, img in image_variants.items():
            if variant_name in ["grayscale", "enhanced", "denoised"]:
                try:
                    # Save temp image for PaddleOCR
                    temp_img_path = f"temp_paddle_{variant_name}.jpg"
                    cv2.imwrite(temp_img_path, img)
                    
                    # Run PaddleOCR
                    paddle_result = paddle_ocr.ocr(temp_img_path, cls=True)
                    if paddle_result and paddle_result[0]:
                        paddle_text = " ".join([line[1][0] for line in paddle_result[0]])
                        avg_confidence = sum([line[1][1] for line in paddle_result[0]]) / len(paddle_result[0])
                        
                        results.append({
                            'text': paddle_text,
                            'method': f'paddle_{variant_name}',
                            'confidence': avg_confidence
                        })
                    
                    # Clean up temp file
                    if os.path.exists(temp_img_path):
                        os.remove(temp_img_path)
                except Exception as e:
                    print(f"PaddleOCR error on {variant_name}: {e}")
                    if os.path.exists(f"temp_paddle_{variant_name}.jpg"):
                        os.remove(f"temp_paddle_{variant_name}.jpg")
    
    return results

def select_best_text_ensemble(extraction_results):
    """Select the best text using an improved ensemble approach with multiple criteria."""
    if not extraction_results:
        return ""
    
    # Calculate comprehensive scores for each result
    scored_results = []
    for result in extraction_results:
        text = result['text']
        method = result['method']
        confidence = result['confidence']
        
        # Skip empty results
        if not text or len(text.strip()) == 0:
            continue
        
        # Score based on multiple validation metrics
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Calculate percentage of recognizable words
        word_count = len(words)
        if word_count == 0:
            continue
            
        recognizable_words = sum(1 for word in words if word in common_english_words)
        word_recognition_score = recognizable_words / word_count if word_count > 0 else 0
        
        # Calculate average word length (penalize very short or very long words)
        avg_word_length = sum(len(word) for word in words) / word_count if word_count > 0 else 0
        length_score = 1.0 - abs(avg_word_length - 5) / 10  # Penalize deviation from average length
        length_score = max(0, min(1, length_score))  # Clamp between 0 and 1
        
        # Calculate character distribution score
        alpha_ratio = sum(c.isalpha() for c in text) / len(text) if len(text) > 0 else 0
        space_ratio = sum(c.isspace() for c in text) / len(text) if len(text) > 0 else 0
        
        # Good text should have a reasonable space-to-character ratio (about 1:5)
        space_score = 1.0 - abs(space_ratio - 0.18) / 0.18
        space_score = max(0, min(1, space_score))
        
        # Check grammar and syntax using TextBlob sentiment as a proxy for coherence
        grammar_score = 0.5  # Default
        try:
            blob = TextBlob(text)
            # If polarity is exactly 0, text might be nonsensical
            grammar_score = 0.5 + abs(blob.sentiment.polarity) * 0.5
        except:
            pass
        
        # Calculate ngram scores (penalize uncommon word combinations)
        ngram_score = 0.5
        if len(words) > 1:
            bigrams = [f"{words[i]} {words[i+1]}" for i in range(len(words)-1)]
            trigrams = [f"{words[i]} {words[i+1]} {words[i+2]}" for i in range(len(words)-2)] if len(words) > 2 else []
            
            # Simple ngram scoring - more sophisticated would use a language model
            for ngram in bigrams + trigrams:
                if any(common_word in ngram for common_word in ["the", "and", "in", "of", "to", "a"]):
                    ngram_score += 0.05
            ngram_score = min(1.0, ngram_score)
        
        # Method-specific boosting (reward more reliable methods based on variant)
        method_boost = 1.0
        if 'easyocr_enhanced' in method or 'easyocr_denoised' in method:
            method_boost = 1.1  # EasyOCR tends to work well with enhanced images
        elif 'tesseract_sauvola' in method or 'tesseract_bilateral' in method:
            method_boost = 1.05  # Tesseract works well with these
        
        # Calculate final weighted score
        final_score = (
            confidence * 0.3 +  # Base confidence
            word_recognition_score * 0.25 +  # Word recognition
            length_score * 0.1 +  # Word length reasonableness
            alpha_ratio * 0.1 +  # Character distribution
            space_score * 0.1 +  # Space distribution
            grammar_score * 0.1 +  # Grammar proxy
            ngram_score * 0.05  # N-gram coherence
        ) * method_boost
        
        scored_results.append({
            'text': text,
            'method': method,
            'score': final_score,
            'confidence': confidence,
            'word_recognition': word_recognition_score,
            'recognizable_words': recognizable_words,
            'total_words': word_count
        })
    
    # Sort by score and select the best result
    if scored_results:
        scored_results.sort(key=lambda x: x['score'], reverse=True)
        
        # Print debugging info for top 3 results
        print("\nTop OCR Results:")
        for i, result in enumerate(scored_results[:3]):
            print(f"{i+1}. Method: {result['method']}")
            print(f"   Score: {result['score']:.2f}, Confidence: {result['confidence']:.2f}")
            print(f"   Word Recognition: {result['word_recognition']:.2f} ({result['recognizable_words']}/{result['total_words']})")
            print(f"   Text: {result['text'][:80]}...")
        
        return scored_results[0]['text']
    
    return ""

def closest_common_word(word, min_length=3, threshold=0.7):
    """Find the closest common English word to the given word with improved matching."""
    if not word or len(word) < min_length:
        return ""
    
    word = word.lower()
    
    # First check if it's already a common word
    if word in common_english_words:
        return word
        
    best_match = ""
    best_score = 0
    
    # Prioritize words of similar length for faster matching
    word_len = len(word)
    potential_matches = [w for w in common_english_words if abs(len(w) - word_len) <= 2]
    
    # If too few potential matches, use all common words
    if len(potential_matches) < 50:
        potential_matches = common_english_words
    
    # Check for edits at beginning/end separately (common in handwriting OCR)
    first_char = word[0]
    potential_first_char_matches = [w for w in potential_matches if w and w[0] == first_char]
    
    # Prioritize words that start with the same letter (common in handwriting)
    for common_word in potential_first_char_matches:
        similarity = word_similarity(word, common_word)
        if similarity > best_score and similarity >= threshold:
            best_score = similarity
            best_match = common_word
    
    # If no good match found, try all potential matches
    if not best_match:
        for common_word in potential_matches:
            similarity = word_similarity(word, common_word)
            if similarity > best_score and similarity >= threshold:
                best_score = similarity
                best_match = common_word
    
    return best_match

def word_similarity(word1, word2):
    """Calculate the similarity between two words with improved algorithm."""
    # Use SequenceMatcher for general similarity
    basic_similarity = SequenceMatcher(None, word1, word2).ratio()
    
    # Boost score if first and last letters match (important in word recognition)
    first_last_match = 0
    if len(word1) > 0 and len(word2) > 0:
        if word1[0] == word2[0]:
            first_last_match += 0.1
        if word1[-1] == word2[-1]:
            first_last_match += 0.1
    
    # Additional adjustment for length difference
    length_diff_penalty = abs(len(word1) - len(word2)) * 0.05
    length_diff_penalty = min(length_diff_penalty, 0.2)  # Cap the penalty
    
    # Calculate final similarity score
    similarity = basic_similarity + first_last_match - length_diff_penalty
    similarity = max(0, min(1, similarity))  # Ensure between 0 and 1
    
    return similarity

def correct_handwriting_ocr(text, context=None):
    """Apply specialized corrections for handwritten text OCR errors with context awareness."""
    if not text:
        return ""
    
    # Keep original text for comparison
    original_text = text
    
    # First pass: Fix common character-level OCR errors
    for error, correction in handwriting_corrections.items():
        text = text.replace(error, correction)
    
    # Split into words for word-by-word corrections
    words = re.findall(r'\b\w+\b', text)
    corrected_words = []
    
    # Create TextBlob for context-aware correction
    try:
        blob = TextBlob(text)
        corrected_text = str(blob.correct())
        corrected_words = re.findall(r'\b\w+\b', corrected_text)
    except:
        corrected_words = words
    
    # Second pass: word-by-word corrections using common English words
    for i, word in enumerate(words):
        # Skip very short words or words that don't need correction
        if len(word) <= 2 or word.lower() in common_english_words:
            continue
        
        # Try to get corrected version from TextBlob result
        if i < len(corrected_words) and corrected_words[i] != word:
            corrected_word = corrected_words[i]
        else:
            # Manual correction for known OCR errors
            corrected_word = word
            for error, correction in handwriting_corrections.items():
                if error in corrected_word:
                    potential_correction = corrected_word.replace(error, correction)
                    if potential_correction.lower() in common_english_words:
                        corrected_word = potential_correction
            
            # Find closest common word if still not recognized
            if corrected_word.lower() not in common_english_words:
                closest_word = closest_common_word(corrected_word)
                if closest_word and closest_word != corrected_word:
                    similarity = word_similarity(corrected_word.lower(), closest_word.lower())
                    if similarity > 0.7:
                        corrected_word = closest_word
        
        # Replace the word in the original text
        pattern = r'\b' + re.escape(word) + r'\b'
        text = re.sub(pattern, corrected_word, text)
    
    # Use context to fix grammar issues
    try:
        # Extract sentences
        sentences = re.split(r'([.!?]+)', text)
        corrected_sentences = []
        
        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                sentence = sentences[i].strip()
                
                if sentence:
                    # Fix capitalization
                    if sentence and sentence[0].islower():
                        sentence = sentence[0].upper() + sentence[1:] if len(sentence) > 1 else sentence.upper()
                    
                    # Fix common grammatical patterns
                    # Replace "I" lowercase
                    sentence = re.sub(r'\bi\b', 'I', sentence)
                    
                    corrected_sentences.append(sentence)
            
            # Add back punctuation
            if i + 1 < len(sentences):
                corrected_sentences.append(sentences[i + 1])
        
        text = "".join(corrected_sentences)
    except Exception as e:
        print(f"Error in grammar correction: {e}")
    
    # Clean up spacing and punctuation
    text = clean_extracted_text(text)
    
    # If text differs too much from original, blend them
    similarity = SequenceMatcher(None, original_text, text).ratio()
    if similarity < 0.5:
        # Blend original and corrected text
        print("Significant correction detected, blending with original text")
        return text  # In this case, we trust the corrections
    
    return text

def clean_extracted_text(text):
    """Clean up spacing and punctuation issues in the extracted text."""
    if not text:
        return ""
    
    # Fix multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Fix spacing around punctuation
    text = re.sub(r'\s+([.,!?:;])', r'\1', text)
    
    # Add space after punctuation if missing
    text = re.sub(r'([.,!?:;])([A-Za-z])', r'\1 \2', text)
    
    # Remove spaces at the beginning and end
    text = text.strip()
    
    return text

def speak_text(text):
    """Convert text to speech using pyttsx3."""
    if not text:
        print("No text to speak.")
        return
        
    engine.say(text)
    engine.runAndWait()

def process_handwritten_text(image_path):
    """Complete pipeline for processing handwritten text from an image."""
    # Load the image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Failed to load image: {image_path}")
        return ""
        
    # Analyze lighting conditions
    lighting_info = analyze_lighting(image)
    
    # Preprocess the image with multiple variants
    preprocessed_variants = preprocess_image_for_handwriting(image, lighting_info)
    
    # Extract text from all variants
    extraction_results = extract_text_from_all_variants(preprocessed_variants)
    
    # Select the best text using ensemble approach
    raw_text = select_best_text_ensemble(extraction_results)
    
    # Apply specialized corrections for handwritten text
    corrected_text = correct_handwriting_ocr(raw_text)
    
    # Print original and corrected text for comparison
    print("\nOriginal Extracted Text:")
    print(raw_text)
    print("\nCorrected Text:")
    print(corrected_text)
    
    return corrected_text

def camera_capture_and_process():
    """Capture image from camera and process the handwritten text."""
    try:
        # Initialize camera
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open camera.")
            return
            
        print("Press 'c' to capture an image, 'q' to quit.")
        
        while True:
            # Read a frame from the camera
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture image.")
                break
                
            # Display the frame
            cv2.imshow('Camera Feed - Press c to capture, q to quit', frame)
            
            # Check for key presses
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('c'):
                # Save the captured image
                temp_img_path = "captured_handwriting.jpg"
                cv2.imwrite(temp_img_path, frame)
                print(f"Image captured and saved to {temp_img_path}")
                
                # Process the image
                print("Processing image...")
                extracted_text = process_handwritten_text(temp_img_path)
                
                # Speak the extracted text
                if extracted_text:
                    print("Speaking extracted text...")
                    speak_text(extracted_text)
                else:
                    print("No text was extracted from the image.")
                
                print("Press 'c' to capture another image, 'q' to quit.")
        
        # Release the camera and close windows
        cap.release()
        cv2.destroyAllWindows()
        
    except Exception as e:
        print(f"Error in camera capture: {e}")

def main():
    """Main function to run the handwritten text recognition system."""
    print("Handwritten Text Recognition System")
    print("===================================")
    print("1. Process an image file")
    print("2. Capture from camera")
    print("3. Quit")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == '1':
        image_path = input("Enter the path to the image file: ")
        if os.path.exists(image_path):
            extracted_text = process_handwritten_text(image_path)
            if extracted_text:
                print("\nDo you want to hear the text? (y/n): ")
                speak_choice = input().lower()
                if speak_choice == 'y':
                    speak_text(extracted_text)
        else:
            print("Error: File not found.")
    
    elif choice == '2':
        camera_capture_and_process()
    
    elif choice == '3':
        print("Exiting program.")
    
    else:
        print("Invalid choice. Please run the program again.")

if __name__ == "__main__":
    # Check for required libraries
    try:
        import pytesseract
        print("pytesseract is installed.")
    except ImportError:
        print("Warning: pytesseract is not installed. Install it for better OCR results:")
        print("pip install pytesseract")
        print("Note: You also need to install Tesseract OCR on your system.")
    
    try:
        import easyocr
        print("easyocr is installed.")
    except ImportError:
        print("Warning: easyocr is not installed. Install it for better OCR results:")
        print("pip install easyocr")
    
    # Run the main function
    main()
            

