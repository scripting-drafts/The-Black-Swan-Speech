from pypdf import PdfReader 
from tqdm import tqdm

class Text_Provider:
    def get_payloads(self):
        '''Returns a list of strings'''
        reader = PdfReader('Taleb Nassim - The Black Swan.pdf') 
        pages = reader.pages[20:] 

        txt = ''.join([page.extract_text() for page in pages])
        txt = txt.split('\n')
        all_txt = []

        for line in tqdm(txt):
            line = line.strip()
            if line.isupper() == False and line is not int():
                all_txt.append(line)

        return all_txt