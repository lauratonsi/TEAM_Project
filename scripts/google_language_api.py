import os
import csv
import json
from pathlib import Path
from google.cloud import language_v1

ROOT = Path(__file__).resolve().parent.parent

CSV_INPUT = str(ROOT / 'data' / 'wiki_text_pulito.csv')
JSON_OUTPUT = str(ROOT / 'data' / 'google_language_analysis.json')


def get_language_client():
    """Create a Google Cloud Language client.
    Requires GOOGLE_APPLICATION_CREDENTIALS environment variable to point to a service account JSON file.
    """
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if not credentials_path:
        raise EnvironmentError('Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path.')
    if not os.path.exists(credentials_path):
        raise FileNotFoundError(f'Credential file not found: {credentials_path}')
    return language_v1.LanguageServiceClient()


def analyze_entities(client, text):
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    response = client.analyze_entities(document=document, encoding_type='UTF8')
    return [
        {
            'name': entity.name,
            'type': language_v1.Entity.Type(entity.type_).name,
            'salience': entity.salience,
            'wikipedia_url': entity.metadata.get('wikipedia_url', ''),
            'mid': entity.metadata.get('mid', ''),
            'mentions': [mention.text.content for mention in entity.mentions],
        }
        for entity in response.entities
    ]


def analyze_syntax(client, text):
    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    response = client.analyze_syntax(document=document, encoding_type='UTF8')
    return [
        {
            'text': token.text.content,
            'part_of_speech': language_v1.PartOfSpeech.Tag(token.part_of_speech.tag).name,
            'dependency_edge': {
                'label': language_v1.DependencyEdge.Label(token.dependency_edge.label).name,
                'head_token_index': token.dependency_edge.head_token_index,
            },
        }
        for token in response.tokens
    ]


def analyze_row(client, city, transport_text, hotels_text):
    result = {'city': city, 'transport_text': transport_text, 'hotels_text': hotels_text}
    if transport_text:
        result['transport_entities'] = analyze_entities(client, transport_text)
        result['transport_syntax'] = analyze_syntax(client, transport_text)
    else:
        result['transport_entities'] = []
        result['transport_syntax'] = []

    if hotels_text:
        result['hotel_entities'] = analyze_entities(client, hotels_text)
    else:
        result['hotel_entities'] = []

    return result


def main():
    client = get_language_client()
    analysis = []

    if not os.path.exists(CSV_INPUT):
        raise FileNotFoundError(f'CSV file not found: {CSV_INPUT}')

    with open(CSV_INPUT, encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            city = row.get('City', '').strip()
            transport_text = row.get('Transport_Text', '').strip()
            hotels_text = row.get('Hotels_Extracted', '').strip()
            if not city:
                continue

            print(f'Analyzing {city}...')
            analysis.append(analyze_row(client, city, transport_text, hotels_text))

    with open(JSON_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)

    print(f'Analysis complete. Results saved to {JSON_OUTPUT}')


if __name__ == '__main__':
    main()
