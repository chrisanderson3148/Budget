def logger(message):
    print(message)
    with open('process_downloads_log', 'a') as f:
        f.write(message+'\n')
