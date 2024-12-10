# This is a sentiment analysis algo 
# that will be used to analyze the sentiment of given news for a given ticker
BATCH_SIZE=8

# Define training data 
#Data are from the Bloomberg Financial News 120k dataset on Hugging Face Datasets
#https://huggingface.co/datasets/genloop/bloomberg_financial_news_120k
#Remember to install the datasets library by running pip install datasets
#Remember to login to Hugging Face by running huggingface-cli login

from datasets import load_dataset
from transformers import pipeline
import pandas as pd


# Load the dataset
dataset = load_dataset("genloop/bloomberg_financial_news_120k")

# Print the keys of the dataset to see available splits
print("Available splits in the dataset:", dataset.keys())
split_name = 'train' if 'train' in dataset else list(dataset.keys())[0]
print(f"Using split: {split_name}")

# Take a subset of the dataset
subset_size = 100 
subset = dataset[split_name].shuffle(seed=42).select(range(subset_size))
# Initialize sentiment analysis pipeline
sentiment_analyzer = pipeline("sentiment-analysis", model="ProsusAI/finbert")

# Basically, we are going to use the pre-trained sentiment analysis model (POSITIVE,NEGATIVE) and based on the score, we will map it to a category
def map_sentiment_to_category(score):
    if score <= -0.75:
        return "Strong Bearish"
    elif -0.75 < score <= -0.25:
        return "Moderately Bearish"
    elif -0.25 < score <= -0.1:
        return "Slightly Bearish"
    elif -0.1 < score < 0.1:
        return "Neutral"
    elif 0.1 <= score < 0.25:
        return "Slightly Bullish"
    elif 0.25 <= score < 0.75:
        return "Moderately Bullish"
    else:
        return "Strong Bullish"

def add_sentiment(example):
    # Combine headline and article for better context
    text = example['Headline'] + " " + example['Article']
    sentiment = sentiment_analyzer(text[:512])[0]  # Truncate to 512 tokens
    category = map_sentiment_to_category(sentiment['score'] * (-1 if sentiment['label'] == 'negative' else 1))
    example['sentiment'] = category
    return example

# Apply sentiment analysis to the subset
updated_subset = subset.map(add_sentiment)

# Convert to pandas DataFrame for easy viewing
df = pd.DataFrame(updated_subset)

# Display the first few rows with the new sentiment column
print(df[['Headline', 'sentiment']].head())

# Save the updated subset
updated_subset.save_to_disk("bloomberg_financial_news_subset_with_sentiment")

# Print some statistics
sentiment_counts = df['sentiment'].value_counts()
print("\n Sentiment Distribution ( % ):")
print(sentiment_counts / len(df) * 100)