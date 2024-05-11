
# STEP 0: IMPORT LIBRARIES ---------------------------------------------------------------------------------------------

import re
import numpy as np
from pytube import extract
from textblob import TextBlob
from nltk.corpus import wordnet as wn
from youtubesearchpython import *
from youtube_transcript_api import YouTubeTranscriptApi
from datetime import datetime

#***********************************************************************************************************************
# STEP 1: DEFINE THE FUNCTIONS WE WILL USE -----------------------------------------------------------------------------

# This function will allow us to calculate the AGE of a youtube video (how long ago a video was uploaded).
def time_string_to_days(time_str):
    # Define regular expression patterns to extract days, months, and years
    seconds_pattern = r'(\d+)\s*second'
    minutes_pattern = r'(\d+)\s*minute'
    hours_pattern = r'(\d+)\s*hour'
    days_pattern = r'(\d+)\s*day'
    months_pattern = r'(\d+)\s*month'
    years_pattern = r'(\d+)\s*year'
    # Find days, months, and years in the time string
    seconds = sum(int(match.group(1)) for match in re.finditer(seconds_pattern, time_str))
    minutes = sum(int(match.group(1)) for match in re.finditer(minutes_pattern, time_str))
    hours = sum(int(match.group(1)) for match in re.finditer(hours_pattern, time_str))
    days = sum(int(match.group(1)) for match in re.finditer(days_pattern, time_str))
    months = sum(int(match.group(1)) for match in re.finditer(months_pattern, time_str))
    years = sum(int(match.group(1)) for match in re.finditer(years_pattern, time_str))
    # Calculate total days
    total_days = seconds / 84600 + minutes / 1440 + hours / 24 + days + months * 30 + years * 365
    return total_days

# This function will allow us to look, for each video transcript, at only the relevant parts (containing our keywords).
# For each sentence is the raw_list, we look if there is a keyword (contained in kw_list). If there is, we store that
# sentence, the previous and the next one in a new list (result_list) so that we can analyse it later. If the sentence
# that contains the keyword happens to be after a sentence that already contained a keyword, the two shall be joined
# together as most likely they are part of the same overall phrase.
def join_sentences_with_keyword(raw_list, kw_list):
    result_list = []
    check_list = []
    i = 0
    n = len(raw_list)
    while i < n-1:
        if raw_list[i] in check_list:
            s = len(result_list)-1
            result_list[s] = result_list[s] + raw_list[i+1]
            i = i+1
        else:
            if i == 0:
                if any(keyword in raw_list[i] for keyword in kw_list):
                    joined_sentences = raw_list[i] + raw_list[i+1]
                    result_list.append(joined_sentences)
                    check_list.append(raw_list[i+1])
                    i = i+1
                else:
                    i = i+1
            elif n-1 > i > 0:
                if any(keyword in raw_list[i] for keyword in kw_list):
                    joined_sentences = raw_list[i-1] + raw_list[i] + raw_list[i + 1]
                    result_list.append(joined_sentences)
                    check_list.append(raw_list[i+1])
                    i = i+1
                else:
                    i = i+1
            else:
                break
    return result_list

# This function derives the synonyms of a word
def get_synonyms(word):
    synonyms = []
    for synset in wn.synsets(word):
        synonyms.extend(synset.lemma_names())
    # Remove duplicates
    synonyms = list(set(synonyms))
    # For each word, also add the version with the first letter capitalized
    synonyms_with_capitalized = [s.capitalize() for s in synonyms]
    # For each word, substitute the "_" with a " "
    word_list = list()
    for word in synonyms_with_capitalized:
        word_clean = word.replace("_", " ")
        word_list.append(word_clean)
    # synonyms.extend(word_list)
    # Add a space before and after the word so that in the transcript we take only these words and not also the words
    # containing these letters
    word_list_final = [" " + s + " " for s in word_list]
    return word_list_final

# This function cleans the transcript of a youtube video from all non-verbal phrases
def clean(transcript_list):
    # Regular expression to match words inside square brackets
    bracket_pattern = r'\[.*?\]'
    # Regular expression to match dots
    dot_pattern = r'\.'
    comma_pattern = r','
    # Let's now clean the transcript
    cleaned_transcript_list = []
    # Iterate through each dictionary in the list
    for item in transcript_list:
        # Check if the 'text' value contains words inside square brackets
        if re.search(bracket_pattern, item['text']):
            # If it does, do not include this dictionary in the cleaned list
            continue
        else:
            # Otherwise, remove dots and commas from the 'text' value
            cleaned_text = re.sub(dot_pattern, '', item['text'])
            cleaned_text = re.sub(comma_pattern, '', cleaned_text)
            item['text'] = cleaned_text
            cleaned_transcript_list.append(item)
    return cleaned_transcript_list

# This function extrapolates the video IDs from their urls
def video_id(value):
    query = urlparse.urlparse(value)
    if query.hostname == 'youtu.be':
        return query.path[1:]
    if query.hostname in ('www.youtube.com', 'youtube.com'):
        if query.path == '/watch':
            p = urlparse.parse_qs(query.query)
            return p['v'][0]
        if query.path[:7] == '/embed/':
            return query.path.split('/')[2]
        if query.path[:3] == '/v/':
            return query.path.split('/')[2]
    # fail?
    return None

#***********************************************************************************************************************
# STEP 2: DEFINE YOUR RESEARCH INTEREST --------------------------------------------------------------------------------
The inputs of this section are two: (i) the period of time and (ii) the keywords that one wants to analyse.

# Starting from the keywords, create a list of relevant words we want to look for in the videos
word = input("Insert the topic you are interested in: ")
synonyms = get_synonyms(word)
print("Synonyms for", word + ":", synonyms)

# Ask the user if they want to add other synonyms
while True:
    choice = input("Do you want to add more synonyms? (yes/no): ")
    if choice.lower() == 'yes':
        new_synonym = input("Enter a synonym: ")
        synonyms.append(new_synonym)
        synonyms.append(new_synonym.capitalize())
    elif choice.lower() == 'no':
        break
    else:
        print("Invalid choice. Please enter 'yes' or 'no'.")

kw_list = synonyms

# Define a function that from these calculates the number of days to which we want to go back in our analysis.
# Indicate the time period of interest
start_date_years = int(input('In which year (01/01/xxxx) do you want the analysis to start? '))
end_date_years = int(input('In which year (31/12/xxxx) do you want the analysis to end? : '))
today = datetime.now()
start_period_date = (today - datetime(start_date_years, 1, 1)).days
end_period_date = (datetime(end_date_years, 12, 31) - today).days

# Indicate the channel IDs of the channels you want to analyse: remember, try to get the "main" points of view in the
# industries/businesses you are interested in.
# Also, consider choosing older/newer channels based on the tme period you are interested in analysing. For instance,
# if I want my analysis to run from 2000, I need to choose channels that we born before 2000s, otherwise we will not be
# able to do so.
channel_id_1 = input('Insert the ID of the channels you are interested in analysing: ')
channel_id_2 = input('Insert the ID of the channels you are interested in analysing: ')
playlist_1 = Playlist(playlist_from_channel_id(channel_id_1))
playlist_2 = Playlist(playlist_from_channel_id(channel_id_2))

# Let's import as many videos as necessary in order to reach the starting date
# For playlist 1
start_date_tracker1 = 0
while playlist_1.hasMoreVideos:
    if start_date_tracker1 < start_period_date:
        playlist_1.getNextVideos() # We get more videos for the playlist
        playlist_1_videos = playlist_1.videos # We start to isolate the last element of the playlist to understand at
        # which date it was uploaded at
        s = len(playlist_1_videos)-1
        video_s = playlist_1_videos[s]
        intermediate1_s = video_s.get('accessibility', None)
        Intermediate2_s = intermediate1_s.get('title', None)
        pattern = r'views(.*)$'  # Define the regular expression pattern: all the durations are in this format
        match = re.search(pattern, Intermediate2_s)  # Find the matching part of the string
        if match:
            period_str = match.group(1).strip()
            total_days = time_string_to_days(period_str)  # Convert the period str into a total number of days
            start_date_tracker1 = total_days
            print(f'Videos Retrieved for Channel 1: {len(playlist_1.videos)}')
    else:
        break

# For playlist 2
start_date_tracker2 = 0
while playlist_2.hasMoreVideos:
    if start_date_tracker2 < start_period_date:
        playlist_2.getNextVideos()
        playlist_2_videos = playlist_2.videos
        s = len(playlist_2_videos)-1
        video_s = playlist_2_videos[s]
        intermediate1_s = video_s.get('accessibility', None)
        Intermediate2_s = intermediate1_s.get('title', None)
        pattern = r'views(.*)$'  # Define the regular expression pattern: all the durations are in this format
        match = re.search(pattern, Intermediate2_s)  # Find the matching part of the string
        if match:
            period_str = match.group(1).strip()
            total_days = time_string_to_days(period_str)  # Convert the period str into a total number of days
            start_date_tracker2 = total_days
            print(f'Videos Retrieved for Channel 2: {len(playlist_2.videos)}')
    else:
        break

# First, let's extract the links and the durations of these playlists.
# We will use the durations to (i) give an information to the user of the total length of videos analysed and (ii) to
# create an unbiased analysis.

# Playlist 1
i = 0
n = len(playlist_1.videos)
times1 = list()
links1 = list()
while i < n:
    video_i = playlist_1.videos[i]
    times1.append(video_i.get('duration', None))
    links1.append(video_i.get('link', None))
    i = i+1

# Playlist 2
i = 0
n = len(playlist_2.videos)
times2 = list()
links2 = list()
while i < n:
    video_i = playlist_2.videos[i]
    times2.append(video_i.get('duration', None))
    links2.append(video_i.get('link', None))
    i = i+1

# NB: This process will eliminate some videos even though they might be later analysed. This means the total duration
# analysed is just an approximation (an underestimation, more precisely) of the real duration analysed. I left the code
# in this way because re-adapting the code would have taken me too much time and this is not a critical feature. More
# importantly, some key information might be contained in those videos, and having an error in the total duration
# is not worth excluding that information.

# Now that we have the total times of the videos, we can build an "unbiased" point of view.

# Playlist 1
playlist1videos_raw = playlist_1.videos
i = len(playlist1videos_raw)-1
periods1 = list()
while i >= 0:
    video_i = playlist1videos_raw[i]
    intermediate1_i = video_i.get('accessibility', None)
    Intermediate2_i = intermediate1_i.get('title', None)
    pattern = r'views(.*)$' # Define the regular expression pattern: all the durations are in this format
    match = re.search(pattern, Intermediate2_i) # Find the matching part of the string
    if match:
        period_str = match.group(1).strip()
        total_days = time_string_to_days(period_str) # Convert the period str into a total number of days
        periods1.append(total_days)
        i = i-1

# Now that we have the period of time when the videos were uploaded, I will delete the "diff" number of videos from the
# end. This is because there are two elements to consider in the "time period": (i) the start, (ii) the end. For (i),
# we already took it into account when downloading the videos --> we want to download them as far as we can until the
# beginning of the starting year. For (ii) we will do it now, using this method I explained above.
filtered_dates1 = [date for date in periods1 if date > end_period_date]
diff = len(playlist1videos_raw)-len(filtered_dates1)
del links1[:diff]
# Now let's do the same for the times and dates lists
del times1[:diff]
del periods1[:diff]

# Now let's calculate the total times for playlist 1.
i = 0
n = len(times1)
times_clean1 = list()
total_seconds1 = 0
while i < n: # This simply cleans the list from all the 'None' elements.
    if times1[i] == None:
        i = i+1
    else:
        times_clean1.append(str(times1[i]))
        i = i+1
i = 0
n = len(times_clean1)
total_seconds1 = 0
while i < n:
    time_elements = times_clean1[i].split(':')
    hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
    minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
    seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
    total_seconds1 = total_seconds1 + hours * 3600 + minutes * 60 + seconds
    i = i+1

# Playlist 2
playlist2videos_raw = playlist_2.videos
i = len(playlist2videos_raw)-1
periods2 = list()
while i >= 0:
    video_i = playlist2videos_raw[i]
    intermediate1_i = video_i.get('accessibility', None)
    Intermediate2_i = intermediate1_i.get('title', None)
    pattern = r'views(.*)$' # Define the regular expression pattern: all the durations are in this format
    match = re.search(pattern, Intermediate2_i) # Find the matching part of the string
    if match:
        period_str = match.group(1).strip()
        total_days = time_string_to_days(period_str) # Convert the period str into a total number of days
        periods2.append(total_days)
        i = i-1

filtered_dates2 = [date for date in periods2 if date > end_period_date]
diff = len(playlist2videos_raw)-len(filtered_dates2)
del links2[:diff]
# Now let's do the same for the times
del times2[:diff]
del periods2[:diff]

# Now let's calculate the total times for playlist 2.
i = 0
n = len(times2)
times_clean2 = list()
total_seconds2 = 0
while i < n: # This simply cleans the list from all the 'None' elements.
    if times2[i] == None:
        i = i+1
    else:
        times_clean2.append(str(times2[i]))
        i = i+1
i = 0
n = len(times_clean2)
total_seconds2 = 0
while i < n:
    time_elements = times_clean2[i].split(':')
    hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
    minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
    seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
    total_seconds2 = total_seconds2 + hours * 3600 + minutes * 60 + seconds
    i = i+1

# Show the use the total time of the videos if we were not to adjust it
print('The total raw duration of the videos would be: ')
print('For playlist one: ', int(total_seconds1/3600), ' hours')
print('For playlist two: ', int(total_seconds2/3600), ' hours')

# Now let's make the two playlist the same total time duration, so that we are not subject to biases.
if total_seconds2 > total_seconds1:
    while total_seconds2 // total_seconds1 > 1:
        step_size = int(total_seconds2/total_seconds1)
        del links2[::step_size]
        del periods2[::step_size]
        del times_clean2[::step_size]
        i = 0 # This simply calculates total_seconds1
        n = len(times_clean1)
        total_seconds1 = 0
        while i < n:
            time_elements = times_clean1[i].split(':')
            hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
            minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
            seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
            total_seconds1 = total_seconds1 + hours * 3600 + minutes * 60 + seconds
            i = i + 1
        i = 0 # This simply calculates total_seconds2
        n = len(times_clean2)
        total_seconds2 = 0
        while i < n:
            time_elements = times_clean2[i].split(':')
            hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
            minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
            seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
            total_seconds2 = total_seconds2 + hours * 3600 + minutes * 60 + seconds
            i = i + 1
else:
    while total_seconds1 // total_seconds2 > 1:
        step_size = int(total_seconds1 / total_seconds2)
        del links1[::step_size]
        del periods1[::step_size]
        del times_clean1[::step_size]
        i = 0
        n = len(times_clean1)
        total_seconds1 = 0
        while i < n:
            time_elements = times_clean1[i].split(':')
            hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
            minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
            seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
            total_seconds1 = total_seconds1 + hours * 3600 + minutes * 60 + seconds
            i = i + 1
        i = 0
        n = len(times_clean2)
        total_seconds2 = 0
        while i < n:
            time_elements = times_clean2[i].split(':')
            hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
            minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
            seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
            total_seconds2 = total_seconds2 + hours * 3600 + minutes * 60 + seconds
            i = i + 1

# Now let's calculate again the total time of the videos that we are going to analyse:
i = 0
n = len(times_clean1)
total_seconds1 = 0
while i < n:
    time_elements = times_clean1[i].split(':')
    hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
    minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
    seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
    total_seconds1 = total_seconds1 + hours * 3600 + minutes * 60 + seconds
    i = i+1
i = 0
n = len(times_clean2)
total_seconds2 = 0
while i < n:
    time_elements = times_clean2[i].split(':')
    hours = int(float(time_elements[0])) if len(time_elements) >= 1 else 0
    minutes = int(float(time_elements[1])) if len(time_elements) >= 2 else 0
    seconds = int(float(time_elements[2])) if len(time_elements) >= 3 else 0
    total_seconds2 = total_seconds2 + hours * 3600 + minutes * 60 + seconds
    i = i+1

# Show the use the total time of videos that will be actually analysed
total_time = total_seconds1 + total_seconds2
print('The total time of the videos that will be analysed is: ', int(total_time/3600), ' hours')

#***********************************************************************************************************************
# # STEP 3: RETRIEVING TRANSCRIPTS -------------------------------------------------------------------------------------

# First, create a list where we will store our results
Sent_Overall_Score = list()
Sent_Pol_Score = list()
Sent_Subj_Score = list()

# First, for each link in the playlists we want to create the video ID.
IDs_1 = list()
IDs_2 = list()
for url in links1:
    IDs_1.append(extract.video_id(url))
for url in links2:
    IDs_2.append(extract.video_id(url))

print(len(IDs_1))
print(len(periods1))
print(len(IDs_2))
print(len(periods2))

# FOR PLAYLIST 1 -------------------------------------------------------------------------------------------------------
# Then, from the raw YT transcript we want to create a list of phrases.
n_obs1 = list()
Sent_Overall_Score = list()
Sent_Subj_Score = list()
Sent_Pol_Score = list()
r = len(IDs_1)-1
while r >= 0:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(IDs_1[r])
        cleaned_transcript = clean(transcript)
# To distinguish the timings of the speech, we are going to use duration of the phrase.
# More specifically, we are going to use the duration of the phrase divided by its number of characters as a proxy of
# whether there is a comma or a dot after that phrase. (HP1: phrases do not interrupt mid-subtitle -> I tested this
# empirically and it is true approx 95% of the time)
# I will not use the duration indicated in the video as it is not accurate (I empirically tested it and does not
# represent at all the reality of timings). I will derive it from the starts

# First, extract the starting times of each phrase
        start = [line['start'] for line in cleaned_transcript]
        duration = [line['duration'] for line in cleaned_transcript]
        end = [x + y for x, y in zip(start, duration)]
        i = 0
        n = len(end) - 2
        diff = list()
        while i < n:
            diff.append(start[i + 1] - end[i])
            i = i + 1
# Then, calculate the duration of each phrase, the number of characters and the key descriptive statistics we are going
# to use in the subsequent calculations
        dur = list()
        n = len(start)-1
        i = 0
        while i < n:
            dur.append(start[i+1]-start[i])
            i = i+1

# Since dur has one element less than the transcript, to make them both of the appropriate lenght I shall remove the
# last element of the transcript (assuming it does not contain any essential information, that to me seems plausible)
        n = len(cleaned_transcript)-1
        del cleaned_transcript[n]

# Now calculate the duration per character, our key metric for inserting commas and dots in the text, and the
# relative statistics we will use to distinguish where to put dots or commas.

# First, we create a list with the length of each world
        words = [line['text'] for line in cleaned_transcript]
        words_length = list()
        for word in words:
            words_length.append(len(word))

# Then we calculate the average duration per character of each word
        dur_per_char = list()
        n = len(words_length)
        i = 0
        while i < n:
            dur_per_char.append(dur[i]/words_length[i])
            i = i+1

# Finally, we calculate keys statistics we are going to use later
        comma_dur = np.quantile(dur_per_char, 0.65)
        dot_dur = np.quantile(dur_per_char, 0.90)

# Now create a loop that adds either commas or dots based on these metrics. In this part of the code, although I
# left it so that one can add also dots and try to reason on them, I will only use commas for simplicity.
        cleaned_text = [line['text'] for line in cleaned_transcript]

        n = len(cleaned_text)-1
        i=0
        while i < n:
            if diff[i] > 0:
                cleaned_text[i] = str(cleaned_text[i] + ',')
                i = i + 1
            elif dot_dur > dur_per_char[i] > comma_dur:
                cleaned_text[i] = str(cleaned_text[i] + ',')
                i = i + 1
            elif dur_per_char[i] > dot_dur:
                cleaned_text[i] = str(cleaned_text[i] + ',')  # I have substituted commas here as well
                i = i + 1
            else:
                i = i + 1

# First, join all the elements of the new list with the correct punctuation.
        cleaned_text = ''.join(cleaned_text)

# Create a list with each phrase as element
        raw_list = cleaned_text.split(',')

# Remove empty strings caused by consecutive periods
        raw_list = [sentence.strip() for sentence in raw_list if sentence.strip()]

# Use the function to create a list of relevant sentences
        filtered_text = join_sentences_with_keyword(raw_list, kw_list)

# Then analyse your data
# First, calculate polarity and subjectivity scores for each "filtered" sentence
        polarity_scores = list()
        subjectivity_scores = list()
        for sentence in filtered_text:
            analyse_text = TextBlob(sentence)
            polar_score=analyse_text.sentiment.polarity
            subj_score=analyse_text.sentiment.subjectivity
            Sent_Pol_Score.append(polar_score)
            Sent_Subj_Score.append(subj_score)
            Sent_Overall_Score.append(polar_score*subj_score)
        print("Element ", r, " processed correctly")
# Store both the information about how many observations were made at each period1 element in another list, so
# that we can reconciliate the observations with the period in which they were made
        n_obs1.append(len(filtered_text))
        r = r-1
# If there is an error, we will skip that video and go on to the next one
    except Exception:
        del periods1[r]
        print("Error in processing the ", r, "th element")
        r = r-1

# Print and store results
print(len(Sent_Overall_Score))
print(len(periods1))
print(n_obs1)
print(Sent_Overall_Score)
print(Sent_Pol_Score)
print(Sent_Subj_Score)
print(periods1)
with open(r'aaaa', 'a') as writer:
    for score in Sent_Overall_Score:
        writer.write(str(score) + ",")
with open(r'aaaa', 'a') as writer:
    for score in Sent_Pol_Score:
        writer.write(str(score) + ",")
with open(r'aaaa', 'a') as writer:
    for score in Sent_Subj_Score:
        writer.write(str(score) + ",")
with open(r'aaaa', 'a') as writer:
    for period in periods1:
        writer.write(str(period) + ",")
with open(r'aaaa', 'a') as writer:
    for obs in n_obs1:
        writer.write(str(obs) + ",")

print('PROCESS ENDED CORRECTLY for playlist 1')

# FOR PLAYLIST 2 -------------------------------------------------------------------------------------------------------
# Then, from the raw YT transcript we want to create a list of phrases.
n_obs2 = list()
Sent_Overall_Score = list()
Sent_Subj_Score = list()
Sent_Pol_Score = list()
r = len(IDs_2)-1
while r >= 0:
    try:
        transcript = YouTubeTranscriptApi.get_transcript(IDs_2[r])
        cleaned_transcript = clean(transcript)

# Following the same logics as before:
# First, extract the key timings of each phrase
        start = [line['start'] for line in cleaned_transcript]
        duration = [line['duration'] for line in cleaned_transcript]
        end = [x + y for x, y in zip(start, duration)]
        i = 0
        n = len(end) - 2
        diff = list()
        while i < n:
            diff.append(start[i + 1] - end[i])
            i = i + 1
# Then, calculate the duration of each phrase, the number of characters and the key descriptive statistics we are going
# to use in the subsequent calculations
        dur = list()
        n = len(start)-1
        i = 0
        while i < n:
            dur.append(start[i+1]-start[i])
            i = i+1

# Since dur has one element less than the transcript, to make them both of the appropriate length I shall remove the
# last element of the transcript (assuming it does not contain any essential information, that to me seems plausible)
        n = len(cleaned_transcript)-1
        del cleaned_transcript[n]

# Now calculate the duration per character, our key metric for inserting commas and dots in the text, and the
# relative statistics we will use to distinguish where to put dots or commas.

# First, we create a list with the length of each world
        words = [line['text'] for line in cleaned_transcript]
        words_length = list()
        for word in words:
            words_length.append(len(word))

# Then we calculate the average duration per character of each word
        dur_per_char = list()
        n = len(words_length)
        i = 0
        while i < n:
            dur_per_char.append(dur[i]/words_length[i])
            i = i+1

# Finally, we calculate keys statistics we are going to use later
        comma_dur = np.quantile(dur_per_char, 0.65)
        dot_dur = np.quantile(dur_per_char, 0.90)

# Now create a loop that adds either commas or dots based on these metrics. In this part of the code, although I
# left it so that one can add also dots and try to reason on them, I will only use commas for simplicity.
        cleaned_text = [line['text'] for line in cleaned_transcript]

        n = len(cleaned_text)-1
        i=0
        while i < n:
            if diff[i] > 0:
                cleaned_text[i] = str(cleaned_text[i] + ',')
                i = i + 1
            elif dot_dur > dur_per_char[i] > comma_dur:
                cleaned_text[i] = str(cleaned_text[i] + ',')
                i = i + 1
            elif dur_per_char[i] > dot_dur:
                cleaned_text[i] = str(cleaned_text[i] + ',')  # I have substituted commas here as well
                i = i + 1
            else:
                i = i + 1

# First, join all the elements of the new list with the correct punctuation.
        cleaned_text = ''.join(cleaned_text)

# Create a list with each phrase as element
        raw_list = cleaned_text.split(',')

# Remove empty strings caused by consecutive periods
        raw_list = [sentence.strip() for sentence in raw_list if sentence.strip()]

# Use the function to create a list of relevant sentences
        filtered_text = join_sentences_with_keyword(raw_list, kw_list)

# Then analyse your data
# First, calculate polarity and subjectivity scores for each "filtered" sentence
        polarity_scores = list()
        subjectivity_scores = list()
        for sentence in filtered_text:
            analyse_text = TextBlob(sentence)
            polar_score=analyse_text.sentiment.polarity
            subj_score=analyse_text.sentiment.subjectivity
            Sent_Pol_Score.append(polar_score)
            Sent_Subj_Score.append(subj_score)
            Sent_Overall_Score.append(polar_score*subj_score)
        print("Element ", r, " processed correctly")
        # Store both the information about how many observations were made at each period1 element in another list, so
        # that we can reconciliate the observations with the period in which they were made
        n_obs2.append(len(filtered_text))
        r = r-1
# If there is an error, we will skip that video and go on to the next one
    except Exception:
        del periods2[r]
        print("Error in processing the ", r, "th element")
        r = r-1

# Store results
with open(r'aaaa', 'a') as writer:
    for score in Sent_Overall_Score:
        writer.write(str(score) + ",")
with open(r'aaaa', 'a') as writer:
    for score in Sent_Pol_Score:
        writer.write(str(score) + ",")
with open(r'aaaa', 'a') as writer:
    for score in Sent_Subj_Score:
        writer.write(str(score) + ",")
with open(r'aaaa', 'a') as writer:
    for period in periods2:
        writer.write(str(period) + ",")
with open(r'aaaa', 'a') as writer:
    for obs in n_obs2:
        writer.write(str(obs) + ",")

print('PROCESS ENDED CORRECTLY for playlist 2')
#***********************************************************************************************************************