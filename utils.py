from datetime import datetime


class Logger(object):
    def __init__(self, file_name, print_to_console=True, append=True):
        self.log_file = open(file_name, ('a' if append else 'w'))
        self.print_to_console = print_to_console

        now_is = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log('\n\n\n\n')
        self.log('*' * (len(now_is) + 18))
        self.log('******** {} ********'.format(now_is))
        self.log('*' * (len(now_is) + 18))
        self.log('\n\n')

    def log(self, message):
        if self.print_to_console:
            print(message)
        self.log_file.write(message + '\n')

    def __del__(self):
        self.log_file.close()
