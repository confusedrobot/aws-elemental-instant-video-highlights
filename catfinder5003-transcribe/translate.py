import logging
import json
import boto3
import os

translate = boto3.client('translate')

def lambda_handler(event, context):
    source_language = 'en'
    target_language = 'es'
    review = 'The cat says meow to me through the window.'
    try:
        # The Lambda function calls the TranslateText operation and passes the 
        # review, the source language, and the target language to get the 
        # translated review. 
        result = translate.translate_text(Text=review, SourceLanguageCode=source_language, TargetLanguageCode=target_language)
        print("Translation output: " + str(result))
    except Exception as e:
        print(response)
        raise Exception("[ErrorMessage]: " + str(e))

if __name__ == '__main__':
    print(lambda_handler(None, None))