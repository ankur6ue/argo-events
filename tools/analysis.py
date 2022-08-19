import pandas
import matplotlib.pyplot as plt
import numpy as np

# This program reads the csv file containing the contents of the mysql database into a dataframe, splits by
# eventtype (sns or sqs), and computes the difference between when the event was sent and when the database
# entry was created. This difference is the total event processing delay. The min and max delay is printed and
# a histogram of the delay is plotted.

df = pandas.read_csv('/home/ankur/Documents/argo_event_record.csv')
# add column headers
df.columns = ['Id', 'PayloadId', 'EventType', 'CustomMessage', 'Author', 'EventTs', 'CreatedAtTs']
# filter for SNS events
df_sns = df[df['EventType'] == 'sns']
# The SNS event sensor selects events with Author field = "David".
# verify the filter worked correctly and author names are only "David"
author_names = df_sns['Author'].unique()
# assert
# len(author_names) == 1
# author_names[0] = "David"

df_sns['CreatedAtTs']= pandas.to_datetime(df_sns['CreatedAtTs']).astype(int)/1e6
df_sns['EventTs']= pandas.to_datetime(df_sns['EventTs']).astype(int)/1e6
df_sns['Lag'] = df_sns['CreatedAtTs'] - df_sns['EventTs']
data = df_sns['Lag']
print("SNS: min={0}, max={1}, mean={2}".format(np.min(data), np.max(data), np.mean(data)))
binwidth = 10
ax = data.plot.hist(bins=np.arange(min(data), max(data) + binwidth, binwidth))
plt.show()

# Now do the same with SQS type
df_sqs = df[df['EventType'] == 'sqs']
# The SQS event sensor selects events with Author field = "Ankur".
# verify the filter worked correctly and author names are only "Ankur"
author_names = df_sqs['Author'].unique()
# assert
# len(author_names) == 1
# author_names[0] = "Ankur"
df_sqs['CreatedAtTs']= pandas.to_datetime(df_sqs['CreatedAtTs']).astype(int)/1e6
df_sqs['EventTs']= pandas.to_datetime(df_sqs['EventTs']).astype(int)/1e6
df_sqs['Lag'] = df_sqs['CreatedAtTs'] - df_sqs['EventTs']
data = df_sqs['Lag']
print("SQS: min={0}, max={1}, mean={2}".format(np.min(data), np.max(data), np.mean(data)))
binwidth = 30
ax =  data.plot.hist(bins=np.arange(min(data), max(data) + binwidth, binwidth))
plt.show()