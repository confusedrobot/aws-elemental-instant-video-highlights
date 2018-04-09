import logging
import json
import boto3
import os
from pprint import pprint
comprehend = boto3.client('comprehend')

def strip (data):
    if any ([isinstance(data, type) for type in [float]]):
        return str(data)
    return False
def stripper (data):
    if isinstance(data, dict):
        newdata = {k: stripper(v) for k, v in data.iteritems()}
        return {k: v for k, v in newdata.iteritems() if not strip(v)}
    elif isinstance(data, list):
        newdata = [stripper(v) for v in data]
        return [v for v in newdata if not strip(v)]
    return data

def lambda_handler(event, context):
    comprehend_dict = {}
    transcript = "Using all right, we could watch that microphone spin for a long time. S so talking back to technology. Can you help us understand the role video plays in your space work ? Well, when we're traveling at seventeen thousand five hundred miles an hour, there's, a lot of data going by, even just looking at there, is below us. And because we're, uh, traveling once around the world every ninety minutes, the earth is processing underneath our orbit. We get to see all over the world, and we're in different places each time we pass over a particular area. So it is amazing amount of data that allows us to capture some of that and high resolution, but actually, inside the space station, were also capturing a lot of data. I date a resolute."
    # source_lang = 'en'
    detect_dominant_language = comprehend.detect_dominant_language(Text=transcript)['Languages'][0]
    comprehend_dict['detect_dominant_language'] = detect_dominant_language
    source_lang = detect_dominant_language['LanguageCode']
    # key_phrases
    key_phrases = comprehend.detect_key_phrases(Text=transcript,LanguageCode=source_lang)['KeyPhrases']
    for key_phrase in key_phrases:
        key_phrase['Score'] = str(key_phrase['Score'])
    comprehend_dict['key_phrases'] = key_phrases
    # sentiment
    detect_sentiment = comprehend.detect_sentiment(Text=transcript,LanguageCode=source_lang)
    comprehend_dict['sentiment'] = detect_sentiment['Sentiment']
    for key,value in detect_sentiment['SentimentScore'].iteritems():
        detect_sentiment['SentimentScore'][key] = str(value)
    comprehend_dict['sentiment_score'] = detect_sentiment['SentimentScore']        
    # detect_entities
    detect_entities = comprehend.detect_entities(Text=transcript,LanguageCode=source_lang)['Entities']
    for detect_entity in detect_entities:
        detect_entity['Score'] = str(detect_entity['Score'])
    comprehend_dict['detect_entities'] = detect_entities

    pprint(comprehend_dict)
if __name__ == '__main__':
    print(lambda_handler(None, None))