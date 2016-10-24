import urllib2
import json
import datetime
import csv
import time
import argparse
import re

app_id = "<FILL IN>"
app_secret = "<FILL IN>" # DO NOT SHARE WITH ANYONE!

access_token = app_id + "|" + app_secret

# regex for detecting smileys: see http://stackoverflow.com/questions/20582030/detect-emoticon-in-a-sentence-using-regex-python#20583383
#emoji_regex = r'[:;=]+[-~]?[()DoOpP]+' # from Eclipse project
eyes, noses, mouths = r":;8BX=", r"-~'^", r")(/\|DP"
emoji_pattern = "[%s][%s]?[%s]" % tuple(map(re.escape, [eyes, noses, mouths]))

smileys = """:-) :) :o) :] :3 :c) :> =] 8) =) :} :^) 
             :D 8-D 8D x-D xD X-D XD =-D =D =-3 =3 B^D""".split()
emoji_list = "|".join(map(re.escape, smileys))
# regex for detecting a URL: see http://stackoverflow.com/questions/700163/detecting-a-naughty-or-nice-url-or-link-in-a-text-string
#url_pattern = r'[^\b]\.([a-zA-Z]{2}|aero|asia|biz|cat|com|coop|edu|gov|info|int|jobs|mil|mobi|museum|name|net|org|pro|tel|travel)[\b/]'
url_pattern = r'https?://\S*'
whitespace_pattern = r'[\n\t ]+'

def request_once(url):
    req = urllib2.Request(url)
    try: 
        response = urllib2.urlopen(req)
        if response.getcode() == 200:
            success = True
        return response.read()
    except Exception, e:
        print e
        print "Error for URL %s: %s" % (url, datetime.datetime.now())
        return None

# Needed to write tricky unicode correctly to csv
def unicode_normalize(text):
    return text.translate({ 0x2018:0x27, 0x2019:0x27, 0x201C:0x22, 0x201D:0x22,
                            0xa0:0x20 }).encode('utf-8')

def getFacebookPageFeedData(page_id, access_token, num_statuses):

    # Construct the URL string; see http://stackoverflow.com/a/37239851 for
    # Reactions parameters
    base = "https://graph.facebook.com/v2.6"
    node = "/%s/posts" % page_id 
    fields = "/?fields=message,link,created_time,type,name,id," + \
            "comments.limit(0).summary(true),shares,reactions" + \
            ".limit(0).summary(true)"
    parameters = "&limit=%s&access_token=%s" % (num_statuses, access_token)
    url = base + node + fields + parameters

    # retrieve data
    url_data = request_once(url)
    data = {}
    if url_data != None:
        data = json.loads(url_data)

    return data

def getReactionsForStatus(status_id, access_token):

    # See http://stackoverflow.com/a/37239851 for Reactions parameters
        # Reactions are only accessable at a single-post endpoint

    base = "https://graph.facebook.com/v2.6"
    node = "/%s" % status_id
    reactions = "/?fields=" \
            "reactions.type(LIKE).limit(0).summary(total_count).as(like)" \
            ",reactions.type(LOVE).limit(0).summary(total_count).as(love)" \
            ",reactions.type(WOW).limit(0).summary(total_count).as(wow)" \
            ",reactions.type(HAHA).limit(0).summary(total_count).as(haha)" \
            ",reactions.type(SAD).limit(0).summary(total_count).as(sad)" \
            ",reactions.type(ANGRY).limit(0).summary(total_count).as(angry)"
    parameters = "&access_token=%s" % access_token
    url = base + node + reactions + parameters

    # retrieve data
    url_data = request_once(url)
    data = {}
    if url_data != None:
        data = json.loads(url_data)

    return data


def getTotalCountByKey(key, table):
    return 0 if key not in table else \
        (0 if 'summary' not in table[key] else \
        (0 if 'total_count' not in table[key]['summary'] else \
        table[key]['summary']['total_count']))

def processFacebookPageFeedStatus(status, access_token):

    # The status is now a Python dictionary, so for top-level items,
    # we can simply call the key.

    # Additionally, some items may not always exist,
    # so must check for existence first

    status_id = status['id']
    status_message = '' if 'message' not in status.keys() else \
            unicode_normalize(status['message'])
    link_name = '' if 'name' not in status.keys() else \
            unicode_normalize(status['name'])
    status_type = status['type']
    status_link = '' if 'link' not in status.keys() else \
            unicode_normalize(status['link'])

    # Time needs special care since a) it's in UTC and
    # b) it's not easy to use in statistical programs.

    status_published = datetime.datetime.strptime(
            status['created_time'],'%Y-%m-%dT%H:%M:%S+0000')
    status_published = status_published + \
            datetime.timedelta(hours=-5) # EST
    status_published = status_published.strftime(
            '%Y-%m-%d %H:%M:%S') # best time format for spreadsheet programs

    # Nested items require chaining dictionary keys.

    num_reactions = getTotalCountByKey('reactions', status)
    num_comments = getTotalCountByKey('comments', status)
    num_shares = 0 if 'shares' not in status else \
            (0 if 'count' not in status['shares'] else \
            status['shares']['count'])

    # Counts of each reaction separately; good for sentiment
    # Only check for reactions if past date of implementation:
    # http://newsroom.fb.com/news/2016/02/reactions-now-available-globally/

    reactions = getReactionsForStatus(status_id, access_token) if \
            status_published > '2016-02-24 00:00:00' else {}

    num_likes = 0 if 'like' not in reactions else \
            reactions['like']['summary']['total_count']

    # Special case: Set number of Likes to Number of reactions for pre-reaction
    # statuses

    num_likes = num_reactions if status_published < '2016-02-24 00:00:00' \
            else num_likes

    num_loves = getTotalCountByKey('love', reactions)
    num_wows = getTotalCountByKey('wow', reactions)
    num_hahas = getTotalCountByKey('haha', reactions)
    num_sads = getTotalCountByKey('sad', reactions)
    num_angrys = getTotalCountByKey('angry', reactions)

    # Return a dictionary of all processed data

    return {"status_id":status_id, "status_message":status_message, "link_name":link_name, "status_type":status_type, "status_link":status_link,
            "status_published":status_published, "num_reactions":num_reactions, "num_comments":num_comments, "num_shares":num_shares,
            "num_likes":num_likes, "num_loves":num_loves, "num_wows":num_wows, "num_hahas":num_hahas, "num_sads":num_sads, "num_angrys":num_angrys}


def prepPost(post_message, max_tokens):
    if not post_message:
        return False
    # remove anything that looks like a URL -- do this BEFORE emoji matching, because they conflict!
    post_message = re.sub(url_pattern, "HTTP-REF", post_message)
    # remove specific emojis
    post_message = re.sub(emoji_list, "", post_message)
    # try to remove remaining emojis based on a pattern
    post_message = re.sub(emoji_pattern, "", post_message) # note, subn can be used for debugging/advanced usage to detect if anything is actually matched
    # remove excess whitespace
    post_message = re.sub(r'\s+', " ", post_message)
    # remove hashtags
    post_message = re.sub(r"#[a-zA-Z0-9]+", "HASHTAG", post_message)
    # remove leading and trailing whitespace
    post_message = post_message.strip()
    # make sure the number of tokens fits our guidelines
    if len(post_message.split()) > max_tokens:
        return False
    # if we still have a message after all of this, add it to the output
    if not post_message:
        return False
    return post_message

def scrapeFacebookPageFeedStatus(page_id, access_token, max_tokens):

    has_next_page = True
    num_processed = 0   # keep a count on how many we've processed
    scrape_starttime = datetime.datetime.now()

    print "\nScraping %s Facebook Page: %s\n" % (page_id, scrape_starttime)

    statuses = getFacebookPageFeedData(page_id, access_token, 100)
    if not statuses:
        print "\nFailed! No posts scraped from this page.\n"
        print "--------------------------------------------------------------"
        return 0

    filename='%s_facebook_statuses_%s.json' %(page_id, datetime.datetime.now().strftime('%Y-%m-%d'))
    with open(filename, 'wb') as file:

        file.write('{"posts":[')
        while has_next_page:
            for status in statuses['data']:

                # Ensure it is a status with the expected metadata
                if 'reactions' in status:
                    processed_status = processFacebookPageFeedStatus(status, access_token)
                    # do not add statuses with empty messages (e.g. photos)
                    post_message = prepPost(processed_status['status_message'], max_tokens)
                    if post_message:
                        if num_processed != 0:
                            file.write(",\n")
                        file.write(json.dumps({ "company":page_id,
                                                "industry":"fast food",
                                                "id":processed_status["status_id"],
                                                "created_time":processed_status["status_published"],
                                                "message":post_message,
                                                "type":status['type'],
                                                "link_name":processed_status["link_name"],
                                                "likes":processed_status["num_likes"],
                                                "loves":processed_status["num_loves"],
                                                "wows":processed_status["num_wows"],
                                                "hahas":processed_status["num_hahas"],
                                                "sads":processed_status["num_sads"],
                                                "angrys":processed_status["num_angrys"],
                                                "comments":processed_status["num_comments"],
                                                "shares":processed_status["num_shares"]
                                              }, file))

                        # output progress occasionally to make sure code is not
                        # stalling
                        num_processed += 1
                        if num_processed % 1000 == 0:
                            print "%s Statuses Processed: %s" % \
                                (num_processed, datetime.datetime.now())

            # if there is no next page, we're done.
            has_next_page = False
            if 'paging' in statuses.keys():
                data = request_once(statuses['paging']['next'])
                if data != None:
                    statuses = json.loads(data)
                    if statuses != None:
                        has_next_page = True

        file.write("]}\n")

        print "\nDone!\n%s Statuses Processed in %s" % \
                (num_processed, datetime.datetime.now() - scrape_starttime)

        return num_processed


if __name__ == '__main__':
    # read in the input file containing a list of facebook pages from the command line
    parser = argparse.ArgumentParser(description="InputFile")
    parser.add_argument('--file', dest='input_file', required=True)
    parser.add_argument('--maxtokens', '-T', dest='max_tokens', required=False, type=int, default=40)
    args = parser.parse_args()
    
    scrape_starttime = datetime.datetime.now()
    pages_processed = 0
    posts_processed = 0
    total_posts_processed = 0

    skipped_pages = []


    #loop through the id list
    with open(args.input_file, 'rb') as input_file:
        for line in input_file.xreadlines():
            line=line.rstrip('\r\n')
            page_id=line
            posts_processed = scrapeFacebookPageFeedStatus(page_id, access_token, args.max_tokens)
            if posts_processed != 0:
                pages_processed += 1
            else:
                skipped_pages.append(page_id)
            total_posts_processed += posts_processed

    print "\nDone!\n%s Posts in %s Pages Scraped in %s" % \
            (total_posts_processed, pages_processed, datetime.datetime.now() - scrape_starttime)

    if skipped_pages:
        print "\nSkipped Pages:\n"
        for skipped in skipped_pages:
            print skipped,"\n"
    else:
        print "No Pages Skipped."
