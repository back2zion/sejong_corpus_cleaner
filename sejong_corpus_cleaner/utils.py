from collections import defaultdict
import subprocess
from bs4 import BeautifulSoup
from pandas import DataFrame


def check_encoding(list_of_paths):
    list_of_encodings = [subprocess.getstatusoutput("file %s" % path)[1]
        for path in list_of_paths]
    return list_of_encodings

def load_texts_as_sentences(filepaths, encoding='utf-16', is_spoken=True):

    if is_spoken:
        loader = load_spoken_text_as_sentences
    else:
        loader = load_written_text_as_sentences

    sentences = []
    for path in filepaths:
        sentences += loader(path, encoding)
    return sentences

def load_written_text_as_sentences(filepath, encoding='utf-16', header=None):

    if not header:
        header = filepath.split('/')[-1][:-4]

    with open(filepath, encoding=encoding) as f:
        text = f.read()
    soup = BeautifulSoup(text, 'lxml')

    sentences = soup.find_all('p')
    sentences = [sent.text.strip() for sent in sentences]
    sentences = [sent for sent in sentences if sent[:len(header)] == header]

    def remove_header(sent):
        sent_ = [eojeol.split('\t', 1)[-1].strip() for eojeol in sent.split('\n') if eojeol.count('\t') == 2]
        sent_ = [eojeol for eojeol in sent_ if eojeol]
        return '\n'.join(sent_)

    sentences = [remove_header(sent).strip() for sent in sentences]
    sentences = [sent for sent in sentences if sent]
    sentences = [sent for sent in sentences if _is_right_form_of_sentence(sent)]

    return sentences

def load_spoken_text_as_sentences(filepath, encoding='utf-16', header=None):

    if not header:
        header = filepath.split('/')[-1][:-4]

    with open(filepath, encoding=encoding) as f:
        text = f.read()
    soup = BeautifulSoup(text, 'lxml')

    sentences = str(soup.find('text'))
    sentences = [sent.split('\t',1)[-1] for sent in sentences.split('\n')]

    soup = BeautifulSoup('\n'.join(sentences), 'lxml')
    sentences = [sent.text.strip() for sent in soup.find_all('s')]
    sentences = [sent for sent in sentences if sent]
    sentences = [sent for sent in sentences if _is_right_form_of_sentence(sent)]

    return sentences

def _is_right_form_of_sentence(sent):
    for eojeol in sent.split('\n'):
        # check "따라서\t따라서/Advecb"
        if eojeol.count('\t') != 1:
            return False
        if not ('/' in eojeol) or not eojeol:
            return False
    return True

def _sentence_to_morphemes(sent):
    words = [
        word.strip() for eojeol in sent.split('\n')
             for word in eojeol.split('\t')[-1].split('+')
    ]
    # because spoken & written text have different word separate (' + ' and '+')
    words = [word if word[0] != '/' else '+'+word for word in words if word if '/' in word]
    return ' '.join(words)

def load_as_morphemes_sentences(paths, is_spoken=True):
    if is_spoken:
        loader = load_spoken_text_as_sentences
    else:
        loader = load_written_text_as_sentences

    sentences_ = []
    for path in paths:
        sentences = loader(path)
        sentences = [_sentence_to_morphemes(sent) for sent in sentences]
        sentences_ += sentences

    return sentences_

def load_as_eojeol_table(paths, is_spoken=True, return_as_dict=False):
    if is_spoken:
        loader = load_spoken_text_as_sentences
    else:
        loader = load_written_text_as_sentences

    counter = defaultdict(int)
    for path in paths:
        sentences = loader(path)
        for sent in sentences:
            for eojeol_morphemes in sent.split('\n'):
                try:
                    eojeol, morphemes = eojeol_morphemes.split('\t')
                    # because spoken & written have difference format
                    if not (' + ' in morphemes):
                        morphemes = morphemes.replace('+', ' + ')
                        morphemes = morphemes.replace('+ /', '+/')
                    morphemes = morphemes.replace(' + ', ' ')
                    counter[(eojeol, morphemes)] += 1
                except:
                    continue

    if return_as_dict:
        return dict(counter)
    return _to_data_frame(counter)

def _to_data_frame(counter):
    def is_compound(morphemes):
        return morphemes.count(' ') > 0

    df = DataFrame(
        [(eojeol, morphemes, count, is_compound(morphemes)) for (eojeol, morphemes), count in
         sorted(counter.items(), key=lambda x:(-x[1], x[0][0]))],
        columns = 'Eojeol morphemes Count Is_compound'.split()
    )
    return df

def write_sentences(sentences, path):
    with open(path, 'w', encoding='utf-8') as f:
        for sent in sentences:
            f.write('%s\n' % sent)

def find_tag_snippets(corpus, tag, count=100, window=2):
    def has_tag(sent, tag):
        return [i for i, wt in enumerate(sent) if wt[1] == tag]

    snippest = []
    for sent in corpus:
        if len(snippest) >= count:
            break
        tag_idxs = has_tag(sent, tag)
        for idx in tag_idxs:
            snippest.append(sent[idx - window : idx + window + 1])
    return snippest[:count]

class Corpus:

    def __init__(self, morpheme_sentence_path, num_sent=-1):
        self.path = morpheme_sentence_path
        self.num_sent = num_sent

    def __iter__(self):
        with open(self.path, encoding='utf-8') as f:
            for i, sent in enumerate(f):
                if self.num_sent > 0 and i > self.num_sent:
                    break
                morph_poss = [tuple(token.rsplit('/', 1)) for token in sent.split()]
                yield morph_poss