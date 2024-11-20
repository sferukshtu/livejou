#!/usr/bin/python3
from config import config, list_options
import requests, re, os, sys, getopt, time
from bs4 import BeautifulSoup
from datetime import datetime
from transliterate import translit, get_available_language_codes
import time, dateutil.parser
import pytablewriter
import codecs
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach()) # forcefully set "utf-8" for stdout and pytablewriter's output unless it is system's locale


def get_days_with_posts(ljyear, months):
    for i in range(0, config()["attempts"]):
        try:
            for i in range(0, config()["attempts"]):
                r = requests.get(ljyear, headers= {"User-Agent":config()["User-Agent"]})
                time.sleep(config()["pause"])
                soup = BeautifulSoup(r.content, 'html.parser')
                if ( soup.find_all('button', {'name':'adult_check'}) ):
                    return False
                else:
                    days_links = []
                    if months == ["all"]:
                        tlinks = soup.find_all('a', {'href': re.compile(r'\/\w{4}\/\w{2}\/\w{2}\/')})
                        days_links = [ tlink['href'] for tlink in tlinks if ljyear in tlink['href']] # to filter out links to other journals/pages
                    else:
                        for m in months:
                            pattern = r'\/\w{4}\/' + m + '\/\w{2}\/'
                            tlinks = soup.find_all('a', {'href': re.compile(pattern)})
                            mlinks = [ tlink['href'] for tlink in tlinks if ljyear + m + "/" in tlink['href'] ]
                            days_links.extend(mlinks)
                    return list(set(days_links))
        except Exception as e:
            e_type, e_object, e_traceback = sys.exc_info()
            print("[get_days_with_posts] connection or parsing error with", ljyear, "(line:", str(e_traceback.tb_lineno) + ")")
            print("reason:", e, "sleeping for "+str(config()["failpause"])+"secs and trying again")
            time.sleep(config()["failpause"])
            continue


def get_month_links_with_posts(ljyear, months):
    for i in range(0, config()["attempts"]):
        try:
            r = requests.get(ljyear, headers= {"User-Agent":config()["User-Agent"]})
            time.sleep(config()["pause"])
            soup = BeautifulSoup(r.content, 'html.parser')
            month_links = []
            if months == ["all"]:
                links = soup.find_all('a', {'href': re.compile(r'\/\w{4}\/\w{2}\/$')})
                month_links = [ link['href'] for link in links if ljyear in link['href']]
            else:
                for m in months:
                    pattern = r'\/\w{4}\/' + m + '\/$'
                    links = soup.find_all('a', {'href': re.compile(pattern)})
                    mlinks = [ link['href'] for link in links if ljyear + m + "/" in link['href']]
                    month_links.extend(mlinks)
            return list(set(month_links))
        except Exception as e:
            e_type, e_object, e_traceback = sys.exc_info()
            print ("[get_month_links_with_posts] connection or parsing error with", ljyear + "/" + month + "/", "(line:", str(e_traceback.tb_lineno) + ")")
            print("reason:", e, "sleeping for "+str(config()["failpause"])+"secs and trying again")
            time.sleep(config()["failpause"])
            continue


def get_month_post_links(lj, year, month):
    post_links = []
    for i in range(0, config()["attempts"]):
        try:
            r = requests.get(lj + year + "/" + month + "/", timeout=(2,5), headers={"User-Agent":config()["User-Agent"]})
            time.sleep(config()["pause"])
            reposts = 0
            soup = BeautifulSoup(r.content, 'html.parser')
            p_links = soup.find_all('a', {'href': re.compile(r'livejournal.com\/(\w+)\.html$')})
            d_links = soup.find_all('a', {'href': re.compile(r'\/\w{4}\/\w{2}\/\w{2}\/')})
            day_hrefs = [ link['href'] for link in d_links if lj + year + "/" + month + "/" in link['href']]
            day_hrefs = list(set(day_hrefs))
            post_hrefs = [ link['href'] for link in p_links ]
            post_links_in_day = {}
            post_links_in_day = get_day_post_links(day_hrefs, post_hrefs, post_links_in_day, str(soup))
            post_links = {}
            matrix = [] # ["is repost", "link", "day", "time", "title"]
            for l in p_links:
                num_comments = 0
                comnts = l.findNext().text
                if comnts == "—":
                    num_comments = l.findNext().findNext().text.split(" ")[0]
                if l.findNext() is not None and re.search(r'comments', comnts) and not re.search(r'\:', comnts):
                    num_comments = l.findNext().text.strip().split(" ")[1]
                if (num_comments == 0):
                    comnts = l.findNextSibling(string=True)
                    if comnts is not None and re.search(r'comments', str(comnts)):
                        num_comments = comnts.strip().split(" ")[1]
                if (l.previousSibling):
                    try:
                        day = post_links_in_day[l['href']]
                    except:
                        day = "01"
                        print(l['href'] + ":", "exception: no unified url's day to link parsed from, thus let it be the 1st day of the month")
                    el = l.findPrevious()
                    hhmm = ""
                    if  el.get('alt') == '[reposted post]':
                        hhmm = el.previousSibling.strip()[:-1]
                        matrix.append(tuple(["repost:", l['href'], day, hhmm, l.text]))
                        reposts += 1
                    else:
                        if re.search(r'\:', el.text) and len(el.text.strip()) == 8:
                            hhmm = el.text.strip()[:-2]
                        else:
                            hhmm = l.previousSibling.strip()[:-1]
                        matrix.append(tuple(["", l['href'], day, hhmm, l.text]))
                    daytime = month + "." + day + "." + year + " " + hhmm.strip()[:-1]
                    daytime = dateutil.parser.parse(daytime)
                    post_links[l['href']] = [daytime, num_comments]
            break
        except Exception as e:
            e_type, e_object, e_traceback = sys.exc_info()
            print("[get_month_post_links] connection or parsing error with", lj + year + "/" + month + "/", "(line:", str(e_traceback.tb_lineno) + ")")
            print("reason:", e, "sleeping for "+str(config()["failpause"])+"secs and trying again")
            time.sleep(config()["failpause"])
            continue
    return post_links, reposts, matrix

def get_day_post_links(day_hrefs, post_hrefs, post_links_in_day, p_month_posts):
    nday = 0
    day_hrefs.sort()
    post_hrefs.sort()
    # days = [d.split("/")[-2] for d in day_hrefs]
    while (nday < len(day_hrefs)):
        day = day_hrefs[nday].split("/")[-2]
        before, day_hrefs[nday], after_this_day = p_month_posts.partition(day_hrefs[nday])
        try:
            before_next_day, day_hrefs[nday+1], after = after_this_day.partition(day_hrefs[nday+1])
        except:
            before_next_day = after_this_day
        for post in post_hrefs:
            if post not in post_links_in_day and post in before_next_day:
                 post_links_in_day[post] = day
                # post_hrefs.remove(post)
        nday += 1
    return post_links_in_day


def is_url_image(url, postlink, fmeta, html):
    image_formats = config()["img_types"]
    try:
        r = requests.head(url, allow_redirects=False, timeout=10, headers= {"User-Agent":config()["User-Agent"]})
    except Exception as e:
        print("..... IMAGE DOWNLOAD FAIILED >> cannot reach this image:", url, "in post", postlink, "reason: ", e)
        print("see also:", fmeta)
        try:
            print_log_in_meta(fmeta, "\t".join([" -- in:", postlink, url, "got no response", " -- now in:", html, "\nfail reason: ", str(e), "\n"]))
        except Exception as e:
            print("cannot write down log about image downloading failure:", e)
        return False
    try:
        if len(r.headers) > 0:
            try:
                if r.headers["content-type"] in image_formats:
                    return True
                else:
                    print("..... IMAGE DOWNLOAD FAIILED >> according to its header's content-type (" + r.headers["content-type"] + ") this is not an image (for me: 404 etc):")
                    print(".....", url, "in post", postlink, "some services are closed for automatic download, may be save this file separately")
                    print("or append this content type in config:", r.headers["content-type"])
                    print("see also:", fmeta)
                    print_log_in_meta(fmeta, "\t".join([" -- in:", postlink, url, r.headers["content-type"], "\n -- now in:", html, "headers: not an image", "\n"]))
                    return False
            except: # if no redirect and no "content-type" in headers (like from photobucket) but it is possibly an image, then save as image
                # print(r.headers)
                print("..... IMAGE DOWNLOAD FAIILED >> I got header's content-type, so this is not an image (anymore):")
                print(".....", url, "in post", postlink, "some services aren't eternal... see also:", fmeta)
                print_log_in_meta(fmeta, "\t".join([" -- in:", postlink, url, "no header's content-type", "\n - now in:", html, "headers: no image data by this url", "\n"]))
                return False # "This Connection is Untrusted" like from https://imgprx.livejournal.net/ will be logged as successful download with 0 size images
    except Exception as e:
        print("..... IMAGE DOWNLOAD FAIILED >> cannot get headers for this image:", url, "in post", postlink, "possible reason: ", "fail reason: ", e)
        print("see also", fmeta)
        print_log_in_meta(fmeta, "\t".join([" -- in:", postlink, url, "no headers", "\n - now in:", html, "failure reason: ", str(e)
        , "\n"]))
        return False

def print_log_in_meta(meta, lines):
    with open(meta, 'a', encoding="utf8") as f:
        f.write(lines)


def create_meta(meta):
    with open(meta, 'w') as f:
        f.write("")


def table_output(matrix, title, headers, file, dump):
    writer = pytablewriter.MarkdownTableWriter()
    writer.column_styles = []
    writer.table_name = title
    writer.headers = headers
    writer.value_matrix = matrix
    writer.enable_ansi_escape = False
    writer.margin = 1
    if file:
        with open(file, 'a', encoding="utf8") as f:
            f.write(writer.dumps())
    if dump:
        return writer.write_table()
    else:
        return ""

def save_post_images(postlink, content, ft, imgs, path_y_m, fmeta, iget):
    log = []
    c = 1
    for i in imgs:
        found_src = 0
        try:
            if i[config()["innerimage_key"]] == config()["innerimage_value"]:
                found_src = 1
        except: # skip images without loading key / exception on the downloading stage
            try:
                if re.search(r'ic\.pics\.livejournal\.com\/', i['src']):
                    found_src = 1
            except: # lj inner ig or tag crashed
                continue
        try:
            if found_src != 0:
                iname = ft + "_"  + str(c) + ".jpg"
                i_url_wrap = i['src'][0:100] # too long sometimes to put it in a log
                ll = []
                if iget:
                    if is_url_image(i['src'], postlink, fmeta, ft + ".htm"):
                        try:
                            idata = requests.get(i['src'], timeout=5, headers= {"User-Agent":config()["User-Agent"]}).content
                        except Exception as e:
                            print("request.get isn't working?... let's skip it so far:", e, postlink)
                            idata = ""
                            continue
                        with open(path_y_m + iname, 'wb') as f:
                            f.write(idata)
                        ll = [i_url_wrap, ft + ".htm", ft + "_" + str(c) + ".jpg"]
                        c += 1
                    else:
                        ll = [i_url_wrap, ft + ".htm", "download failed"]
                else:       
                    ll = [i_url_wrap, ft + ".htm", "download skipped"]    
                log.append(ll)
                content = str(content).replace(i['src'], iname)
        except Exception as e:
            e_type, e_object, e_traceback = sys.exc_info()
            print("Img processing error", postlink, "reason:", e, "(line:", str(e_traceback.tb_lineno), ")")
    return log, content 


def save_post(postlink, stime, iget, path_y_m, fmeta):
    for i in range(0, config()["attempts"]):
        try:
            r = requests.get(postlink, timeout=5, headers= {"User-Agent":config()["User-Agent"]})
            time.sleep(config()["pause"])
            imgs = []
            e = None
            try:
                soup = BeautifulSoup(r.content, 'html.parser')
            except Exception as e:
                print(e)
                # even with r as <Response [200]> LJ can stop loading html, therefore we persist here:
                print ("Responce 200 is gotten for", postlink, "but html is empty... sleeping for "+str(config()["failpause"])+"sec and trying again... " + str(i))
                print ("If all attempts fail then try later, with another year/month(s) (so far)")
                time.sleep(config()["failpause"])
                continue
            if e is None:
                title = soup.find('meta', attrs={'property': config()["usertitle_meta_property"]})
                title = title['content']
                post = None
                for t, c in config()["usercontent_classes"].items():
                    if (len(c)) > 0:
                        for a in c:
                            post = soup.find(t, {'class' : a})
                            if post is not None:
                                break
                    else:
                        post = soup.find(t)
                    if post is not None:
                        break

                if post:
                    try:
                        imgs = post.find_all('img')
                    except:
                        imgs = []

                try:
                    lat_title = translit(title, reversed=True)
                except:
                    lat_title = title
                lat_title = lat_title.replace(" ","_")
                lat_title = re.sub('[^a-zA-Z0-9_]+', '', lat_title)
                if len(lat_title) > 50:
                    lat_title = lat_title[0:50]
                ft = stime.strftime("%d") + "_" + stime.strftime("%H") + "-" + stime.strftime("%M") + "__" + lat_title

                t_links = []
                tags = []
                try:
                    tags = soup.find_all('meta', attrs={'property': config()["tag_meta_property"]})
                    for t in tags:
                        tags.append(t['content'])
                except:
                    # NB: "title":"" here is necessaty to skip a list of all-journal tags!
                    t_links = soup.find_all("a", {"rel":"tag", "href":re.compile(r'livejournal\.com\/tag\/'), "title":""}) 
                    if t_links is None:
                        t_links = []
                    else:
                        tags = [link.text for link in t_links]

                alltags = ",".join(tags)[0:100]
                tgs = "no tags"
                if tags:
                    tgs = "<p><b>Tags: </b>" + ", ".join(tags)

                ilog = []
                if post is None:
                    warning = "-"*100 + "\n !! POST's STYLE: no content parsed! please add post content's style in config (\"usercontent_classes\"): \n" + "-"*100 + " " + postlink
                    print (warning)
                else:
                    for div in post.find_all("div", {"class":config()["adv"]}):
                        div.decompose()
                    try:
                        if soup.find_all("span"):
                            for span in soup.find_all("span"):
                                span.decompose()
                        if soup.find_all("a", {"rel":"tag"}):
                            for a in soup.find_all("a", {"rel":"tag"}):
                                a.decompose()                            
                        if soup.find("div", {"class":"ljtags"}):
                            soup.find("div", {"class":"ljtags"}).decompose()                            
                    except Exception as e:
                        #print("something weird with LJ rubbish code?...", e, postlink)
                        continue
                    ilog, post = save_post_images(postlink, post, ft, imgs, path_y_m, fmeta, iget)    
                
                content = "<html><body><h2>"+title+"</h2><time>"+ str(stime) +"</time>"+str(post)+tgs+"<p>url: "+postlink+"</body></html>"
                content = BeautifulSoup(content, "html.parser").prettify()                
                fname = path_y_m + ft + ".htm"
                with open(fname, 'w', encoding="utf8") as f:
                    f.write(content)
                title = title[0:100]
                row = [ title, alltags ]
                return row, ilog

        except Exception as e:
            e_type, e_object, e_traceback = sys.exc_info()
            print("Network or parsing error with", postlink, "reason:", e, "(line:", str(e_traceback.tb_lineno) + ")")
            print("sleeping for "+str(config()["failpause"])+"secs and trying again... " + str(i))
            print("(or interrupt with Ctrl+C)")
            time.sleep(config()["failpause"])
            continue


def main(argv):
    ljuser = ""
    this_year = str(datetime.now().year)
    months = str(datetime.now().month)
    try:
        opts, arg = getopt.getopt(argv, "j:s:i:a:y:m:h", ["journal=", "stats=", "images", "all=", "years=", "months=", "help="])
    except getopt.GetoptError as e:
        print (e, "-j [--journal] option is necessary, all options: -j, -s, -i, -a, -y, -m, -h (or --journal, --stats, --images, --all, --year, --months, --help)")
        list_options()
        sys.exit(2)
    years = [this_year]
    stats = ""
    iget = ""
    for opt, arg in opts:
        if opt in ("-s", "--stats"):       stats = arg
        if opt in ("-i", "--images"):      iget = arg
        if opt in ("-j", "--journal"):     ljuser = arg
        if opt in ("-y", "--year"):        years = [y.strip() for y in arg.split(",")]
        if opt in ("-m", "--months"):      months = [m.strip() for m in arg.split(",")]
        if opt in ("-a", "--all"):         years = [str(y) for y in range(int(years[0]),int(this_year) + 1)]
        if opt in ("-h", "--help"):
            list_options()
            sys.exit(2)

    if ljuser == "":
        print (">> usage: %s -j [lj username] - this option is necessary!\n" % sys.argv[0])
        list_options()
        sys.exit(2)
    if months != ["all"]:
        months_1 = ["0"+m for m in months if len(m)==1]
        months_2 = [m for m in months if len(m)==2]
        months = months_1
        months.extend(months_2)

    mm = [1 for m in months if m not in ["01","02","03","04","05","06","07","08","09","10","11","12","all"]]
    if len(mm) > 0:
        print ("usage: %s -m [months] - looks like those are not months like 01, 02 etc or all for all months?.. I stop...\n" % sys.argv[0])
        sys.exit(2)

    input_opts = [opt+" "+arg for opt, arg in opts]
    print("Your input: " , " ".join(sys.argv[1:]))
    print("I've got input options as: " , (" ").join(input_opts) , "\n\t or ask help:\n" , sys.argv[0] ," -h")
    if stats != "":
        msg = "Thus gathering only post statistics of " + ljuser + "`s posts for year(s): " + (",").join(years) + " and month(s): " + (",").join(months) + " - proceed? (Y/n) "
    else:
        if iget == "":
            msg = "Thus downloading " + ljuser + "`s posts WITHOUT IMAGES for year(s): " + (",").join(years) + " and month(s): " + (",").join(months) + " - proceed? (Y/n) "
        else:
            msg = "Thus downloading " + ljuser + "`s posts WITH IMAGES for year(s): " + (",").join(years) + " and month(s): " + (",").join(months) + " - proceed? (Y/n) "

    check = input(msg)
    if check == "" or check == "Y" or check == "y":
        path_u = os.getcwd() + "/" + ljuser + "/"
        if stats == "":
            print ("\ncreating directory", ljuser, "unless it exists, gathering data...")
            if not os.path.exists(path_u):
                os.makedirs(path_u)
        lj = "https://" + ljuser + ".livejournal.com/"
        reposts = 0
        for year in years:
            yreposts = 0
            ylines = []
            ljyear = lj + year + "/"
            days_links = get_days_with_posts(ljyear, months)
            if days_links:
                path_y = path_u + year + "/"
                ymeta = path_y + "Meta-" + year + ".txt"
                if not os.path.exists(path_y):
                    os.makedirs(path_y)
                create_meta(ymeta)
                print("-"*100)
                ylines.append("-"*100)
                line = " ".join(["-", str(len(days_links)), "days with posts during", year, "in months:", (",").join(months)])
                ylines.append(line)
                print(line)
                month_links = get_month_links_with_posts(ljyear, months)
                pmonths = [m.split("/")[-2] for m in month_links]
                pmonths.sort()
                line = " ".join([str(len(month_links)), "months with posts during", year, "these months are:", (",").join(pmonths), "...\n"])
                ylines.append(line)
                print(line)
                print("getting all post links & their dates for", year, "in months ^^^^^^^")
                y_posts = 0
                month_links.sort()
                print_log_in_meta(ymeta, "\n".join(list(ylines)))

                for molink in month_links:
                    this_month = molink.split("/")[-2]
                    ts = time.time()
                    post_links, m_reposts, matrix = get_month_post_links(lj, year, this_month)
                    line = "\n#### crawling through posts data during " + str(round((time.time() - ts),1)) + " secs for month " + this_month + "...\n"
                    print(line)
                    ts = time.time()
                    print_log_in_meta(ymeta, line)
                    title = "Posts in month " + this_month + ":"
                    titlerow = ["is repost", "link", "day", "time", "title"]
                    if stats != "":
                        table_output(matrix, title, titlerow, "", 1)    # output in STDOUT
                    else:
                        table_output(matrix, title, titlerow, ymeta, "")# output in file (ymeta)
                    ylines = []
                    line = " ".join(["-", str(len(post_links)-m_reposts), "post(s) and", str(m_reposts), "reposts in", this_month, "month for", year])
                    ylines.append(line)
                    print(line)

                    yreposts += m_reposts
                    y_posts += len(post_links)

                    if stats == "":
                        pmatrix = []
                        imatrix = []
                        path_y_m = path_y + this_month + "/"
                        meta = path_y_m + "Meta-" + year + "-" + this_month + ".txt"
                        title = " ".join(["\n>>>> posts for", this_month, "in", year, ":" ])
                        if not os.path.exists(path_y_m):
                            os.makedirs(path_y_m)
                        create_meta(meta)
                        fmeta = path_y + "Failed_image_downloads" + year + "-" + this_month + ".txt"
                        create_meta(meta)
                        for post_link, day_and_comm in post_links.items():
                            stime, num_com = day_and_comm
                            plog, ilog = save_post(post_link, stime, iget, path_y_m, fmeta)
                            plog.insert(0, post_link)
                            plog.insert(0, stime.strftime("%H:%M"))
                            plog.insert(0, stime.strftime("%d"))
                            repost = "Y"
                            if ljuser not in post_link:
                                repost = "repost"
                            plog.append(repost)
                            plog.append(len(ilog))
                            plog.append(num_com)
                            pmatrix.append(tuple(plog))
                            for item in ilog:
                                item.insert(0, post_link)
                                item.insert(0, stime.strftime("%H:%M"))
                                item.insert(0, stime.strftime("%d"))
                                imatrix.append(tuple(item))
                        table_output(pmatrix, title, ["day", "time", "post", "title", "tags", "own", "imgs", "comnts"], meta, 1)
                        ititle = " ".join(["\n>>>>>>>> images in posts for", this_month, "in", year, ":" ])
                        if len(imatrix) > 0:
                            table_output(imatrix, ititle, ["day", "time", "post", "image original src (url may be trancated)", "post html dowloaded", "post image downloaded"], meta, 1)
                        else:
                            print(ititle, "\n\t None downloaded")
                            print_log_in_meta(meta,  "\n".join([ititle, "\t None downloaded"]))
                        line = "#### downloaded posts data in " + str(round((time.time() - ts),1)) + " secs for month " + this_month + "\n"
                        ylines.append(line)
                        print(line)
                        print_log_in_meta(ymeta, "\n".join(list(ylines)))
                line = " ".join(["\n -- overall", str(y_posts-yreposts), "post(s) and", str(yreposts), "reposts in", year, "and month(s):", (",").join(months), "\n", "-"*100])
                print(line)
                print_log_in_meta(ymeta, line)
            else:
                print("-"*100 +"\nHuh... Banned? Or...? there are 3 versions, good and bad:")
                print("-"*100 +"\n1. good: there are no posts or journal entries according to your input (given journal, year(s) or period of time)")
                print("\n2. bad: I'm banned... you've used me carelessly!")
                print("\n3. good: if you're the journal's owner please untick the option that your content is for adults if it is so")
                print("- only after that I may look through your journal __unless I'm banned__")
                sys.exit(2)
    else:
        print("Ok, I stoppppp")
        sys.exit(2)


if __name__ == '__main__':
    main(sys.argv[1:])
