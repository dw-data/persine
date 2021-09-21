import time
import re
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from urllib.parse import urlparse
from urllib.parse import quote_plus
from .bridge import BaseBridge

class AmazonBridge(BaseBridge):
    """A bridge that interacts with and scrapes Amazon"""


    def __init__(self, driver):
        self.driver = driver
        driver.set_script_timeout(100)

    def __scrape_search_results(self):
        return self.driver.execute_script(
            """
            return [...document.querySelectorAll(".s-result-item")].map((d, i) => {
                let data = {...d.dataset}
                try { data['url'] = d.querySelector('a')['href']; } catch(err) {}
                try { data['img'] = d.querySelector('img')['src']; } catch(err) {}
                try { data['asin'] = d.getAttribute('data-asin'); } catch(err) {}
                try { data['asin'] = data['asin'] || d.querySelector('[data-asin]').getAttribute('data-asin') } catch(err) {}
                try { data['title'] = d.querySelector('[data-click-el="title"]').innerText; } catch(err) {}
                try { data['title'] = data['title'] || d.querySelector('h2').innerText.trim(); } catch(err) {}
                try { data['is_sponsored'] = d.querySelector('[data-component-type="sp-sponsored-result"]') != null; } catch(err) {}
                try { data['stars'] = d.querySelector('[aria-label*="out of 5 stars"]').ariaLabel; } catch(err) {}
                try { data['ratings'] = d.querySelector('[aria-label*="out of 5 stars"] + span').ariaLabel; } catch(err) {}
                try { data['price'] = d.querySelector('.a-price .a-offscreen').innerText; } catch(err) {}
                try { data['old_price'] = d.querySelector('.a-price[data-a-strike="true"] .a-offscreen').innerText; } catch(err) {}
                try { data['price_range'] = d.querySelectorAll('.a-price-range .a-price .a-offscreen')[0].innerText + " - " + d.querySelectorAll('.a-price-range .a-price .a-offscreen')[1].innerText } catch(err) {}
                try { data['free_shipping'] = d.querySelector('[aria-label*="shipping"]') != null; } catch(err) {}
                try { data['is_prime'] = d.querySelector('.a-icon-prime') != null; } catch(err) {}
                return data;
                });
        """
        )  # noqa: E501


    def __scrape_suggested_products(self):

        return self.driver.execute_async_script(
            """                
            let onComplete = arguments[0];

            function getItemDetails(d) {

                let section = d.closest(".a-carousel-container")
                let data = {}

                try { data['title'] = d.querySelector('img')['alt']; } catch(err) {}
                try { data['title'] = d.querySelector('.pba-lob-bundle-title .a-truncate-full').innerText; } catch(err) {}
                try { data['title'] = d.querySelector('.p13n-sc-truncated').innerText; } catch(err) {}
                try { data['asin'] = JSON.parse(d.querySelector("div.p13n-asin").dataset['p13nAsinMetadata'])['asin'] } catch(err) {}
                try { data['url'] = d.querySelector('a.a-link-normal')['href']; } catch(err) {}
                
                try { 
                        let idRegExp =  new RegExp(".*/dp/([\\\w\\\d]+)/.*", "g");
                        console.log(idRegExp);
                        console.log(data["url"]);
                        let match = idRegExp.exec(data["url"]);
                        console.log(match);
                        data['product_id'] = match[1];
                } catch(err) {}

                try { data['img'] = d.querySelector('img')['src']; } catch(err) {}
                try { section.querySelector("h2 .sp_desktop_sponsored_label").remove() } catch(err) {}
                try { section.querySelector("h2 a").remove() } catch(err) {}
                try { data['section_title'] = section.querySelector(".a-carousel-heading").innerText; } catch(err) {}
                try { data['is_sponsored'] = section.innerText.indexOf("Sponsored") != -1 } catch(err) {}
                try { data['stars'] = d.querySelector('[title*="out of 5 stars"]').title; } catch(err) {}
                try { data['review_count'] = d.querySelector('[[title*="out of 5 stars"] .a-size-small').innerText; } catch(err) {}

                if(!data['stars']) {
                    try { data['stars'] = d.querySelector('.adReviewLink i').classList[2]; } catch(err) {}
                }
                if(!data['review_count']) {
                    try { data['review_count'] = d.querySelector('.adReviewLink span').innerText; } catch(err) {}
                }

                try { data['best_seller'] = d.querySelector('.p13n-best-seller').innerText; } catch(err) {}
                try { data['price'] = d.querySelector('.a-price .a-offscreen').innerText.trim(); } catch(err) {}
                try { data['price'] = d.querySelector('.p13n-sc-price,.a-color-price').innerText.trim(); } catch(err) {}
                try { data['free_shipping'] = d.innerText.indexOf("FREE shipping") != -1 } catch(err) {}
                try { data['is_prime'] = d.querySelector('.a-icon-prime') != null; } catch(err) {}
                return data;    
            }

            function getCarouselCurrentContents(root, step) {
                return [...root.querySelectorAll(".a-carousel-card:not(.vse-video-card)[aria-hidden='false']")].map((d, i) => {
                    let data = getItemDetails(d)
                    data['index'] = i;
                    data['pagination'] = step;
                    return data; 
                });
            }

            async function getContentsOfCarousel(root, previousFirst, step=0) {
                if(step > 20) {
                    return Promise.resolve([])
                }
                if(!root.offsetParent) {
                    console.log(root.offsetParent)
                    return Promise.resolve([])
                }
                return new Promise((resolve, reject) => {
                    let contents = getCarouselCurrentContents(root, step)
                    let firstVisible = parseFloat(root.querySelector(".a-carousel-firstvisibleitem").value)
                    firstVisible = firstVisible == "" ? 1 : parseInt(firstVisible)
                    if(firstVisible != 1 || step == 0) {
                        console.log('scrolling to', root)
                        root.scrollIntoView()
                        root.querySelector(".a-carousel-goto-nextpage").click()

                        let waitUntilReady = setInterval(function() {
                            let emptyCarouselCards = root.querySelectorAll(".a-carousel-card-empty[aria-hidden='false']")
                            let isLoaded = emptyCarouselCards.length == 0;
                            console.log("isLoaded?", isLoaded);
                            if (isLoaded) {
                                console.log("scraping carrousel", root);
                                clearInterval(waitUntilReady);
                                getContentsOfCarousel(root, firstVisible, step + 1)
                                    .then(nextPageContents => {
                                        resolve([...contents, ...nextPageContents]);
                                    })
                            } 
                            else {
                                console.log("working");
                            }
                        }, 200);
                    } else {
                        resolve(contents)
                    }
                })
            }

            async function scrapePage() {
                let results = [];
                let buttons = [...document.querySelectorAll(".a-carousel-goto-nextpage")]
                let roots = buttons.map(b => {
                    let root = b.closest(".a-carousel-container")
                    root.style.borderWidth = '10px'
                    root.style.borderColor = 'magenta'
                    root.style.borderStyle = 'solid'
                    root.style.background = '#fff880'
                    return root
                })

                for(let i=0; i < roots.length; i++) {

                    let carouselOptions = JSON.parse(
                        roots[i].getAttribute("data-a-carousel-options")
                    );

                    if (carouselOptions["name"] === "rich-product-information-carousel") {
                        console.log("ignoring details carousel");
                        continue;
                    }

                    results = results.concat(await getContentsOfCarousel(roots[i]));
                    roots[i].style.background = '#c7ff80'
                };

                onComplete(results)
            }

            scrapePage()
            """
        )  # noqa: E501


    def __force_page_contents_load(self):

        # Scrolls over the entirety of the page,
        # revealing all possible carousels

        self.driver.execute_script(
            """
            window.scrollTo({
                top: document.body.scrollHeight,
                left: 0,
                behavior: 'smooth'
            });

            """

        )





    def __scrape_product_info(self):

        def scrape_product_category(driver):
            div = driver.find_element_by_css_selector("#wayfinding-breadcrumbs_container")
            nav = div.find_element_by_css_selector(".a-unordered-list")
            categories = nav.find_elements_by_css_selector(".a-link-normal")
            categories = [category.text for category in categories]
            return dict(enumerate(categories))


        def scrape_product_id(driver):
            url = driver.current_url
            product_id = re.search(".*/dp/([\w\d]+)/.*", url).group(1)
            return product_id


        def scrape_product_name(driver):
            return driver.find_element_by_css_selector("span#productTitle").text

        
        def scrape_product_authors(driver):
            product_authors = driver.find_elements_by_css_selector("a.authorNameLink")
            product_authors = [author.text for author in product_authors]
            return product_authors


        def scrape_product_prices(driver):
            try:
                div_formats = driver.find_element_by_css_selector("div#formats")
                format_buttons = div_formats.find_elements_by_css_selector("span.a-button")
                formats = [ 
                    button.find_element_by_css_selector("a.a-button-text > span").text 
                    for button in format_buttons
                ]
                prices = [ 
                           button.find_element_by_css_selector("span.a-color-price").text 
                           if 'a-button-selected' in button.get_attribute('class').split()
                           else button.find_element_by_css_selector("span.a-color-secondary").text
                           for button in format_buttons
                ]
            
            except NoSuchElementException: 
                # Format for pre-order items
                ul_formats = driver.find_element_by_css_selector("ul#mediaTabs_tabSet")
                format_tabs = ul_formats.find_elements_by_css_selector(".mediaTab_heading:not(.otherSellers)")
                formats = [
                    tab.find_element_by_css_selector("span.mediaTab_title").text 
                    for tab in format_tabs
                ]
                prices = [
                    tab.find_element_by_css_selector("span.mediaTab_subtitle").text 
                    for tab in format_tabs
                ]


            return (dict(zip(formats, prices)))


        def scrape_product_description(driver):
            frame = self.driver.find_element_by_css_selector("#bookDesc_iframe")
            self.driver.switch_to.frame(frame) # We have to enter the iFrame
            desc = self.driver.find_elements_by_css_selector("#iframeContent > *")
            product_description = "\n".join([item.text for item in desc])
            self.driver.switch_to.default_content() # Leave iframe


        def scrape_product_details(driver):

            def is_audiobook(driver):
                try:
                    formats = driver.find_element_by_css_selector("div#formats")
                except NoSuchElementException: 
                    formats = driver.find_element_by_css_selector("ul#mediaTabs_tabSet")

                try:
                    selected = formats.find_element_by_css_selector(".selected")
                except NoSuchElementException:
                    selected = formats.find_element_by_css_selector(".a-active")

                if selected.find_elements_by_css_selector('.audible_mm_title'):
                    return True
                else:
                    return False



            def get_book_details(driver):

                div = driver.find_element_by_css_selector("div#detailBullets_feature_div")
                labels = div.find_elements_by_css_selector("span.a-text-bold")
                
                values = []

                for label in labels:

                    label_text = label.text.replace(":","").strip() 

                    parent = label.find_element_by_xpath("..") # xpath for parent
                    siblings = parent.find_elements_by_css_selector("*") # all children of parent

                    if label_text not in ["Customer Reviews", "Best Sellers Rank"]:
                        assert len(siblings) == 2
                        value = siblings[1] # First sibling is the label, second is the value
                        values.append(value.text.replace(":","").strip())

                    else:               

                        if label_text == "Best Sellers Rank":

                            value = {}

                            # General ranking (if any):
                            string = parent.text.split(":")[1]
                            match = re.search("#([\d,]+) in (.*) \(.*", string)
                            position = match.group(1).strip().replace(",", "")
                            category = match.group(2).strip()

                            value[category] = position

                            # Category specific rankings
                            rankings = parent.find_elements_by_css_selector("li")

                            for ranking in rankings:

                                match = re.search("#([\d,]+) in (.*)", ranking.text)
                                position = match.group(1).strip()
                                category = match.group(2).strip()

                                value[category] = position

                            values.append(value)

                        elif label_text == "Customer Reviews":

                            value = {}

                            average = parent.find_element_by_css_selector("#acrPopover").get_attribute("title")
                            count = parent.find_element_by_css_selector("#acrCustomerReviewText").text

                            value["average"] = average
                            value["count"] = count

                            values.append(value)
      
                labels = [label.text.replace(":","").strip() for label in labels]

                return dict(zip(labels, values))


            def get_audiobook_details(driver):
                div = driver.find_element_by_css_selector("div#audibleProductDetails")
                trs = div.find_elements_by_css_selector("tr")
                
                labels = []
                values = []

                for row in trs:

                    # TO DO - get ranking positions
                    label = row.find_element_by_css_selector("th")
                    label_classes = label.get_attribute("class").split()

                    if 'prodDetSectionEntry' in label_classes: # This means that the row is about the product rankings
                        
                        value = {}

                        rankings = row.find_element_by_css_selector("td")
                        for ranking in rankings.find_elements_by_css_selector("span"):
                                match = re.search("#([\d,]+) in (.*)", ranking.text)
                                position = match.group(1).strip()
                                category = match.group(2).strip()

                                value[category] = position

                        values.append(value)


                    else:
                        value = row.find_element_by_css_selector("td").text


                labels = [label.text for label in labels]
                    
                return dict(zip(labels, values))


            if is_audiobook(driver):
                return get_audiobook_details(driver)

            else:
                return get_book_details(driver)


        driver = self.driver
        
        data = {
            "product_id": scrape_product_id(driver),
            "product_description": scrape_product_description(driver),
            "product_name": scrape_product_name(driver),
            "product_authors": scrape_product_authors(driver),
            "producy_price": scrape_product_prices(driver),
            "product_categories": scrape_product_category(driver),
            "product_details": scrape_product_details(driver)
        }

        return data


    def __scrape_raw_carousel_data(self):
        return self.driver.execute_script("""
        return [...document.querySelectorAll("[data-a-carousel-options*='}']")].map(d => {
            return {...d.dataset}
        })
        """)


    def get_data(self):
        parsed = urlparse(self.driver.current_url)
        if parsed.path.startswith("/s"):
            return {
                "page_type": "search",
                "query": self.driver.find_element_by_css_selector(
                    ".nav-input"
                ).get_attribute("value"),
                "recommendations": self.__scrape_search_results(),
            }
        elif parsed.path == "/":
            return {
                "page_type": "homepage",
                "recommendations": []
            }
        else:
            return {
                "page_type": "product",
                "product_info": self.__scrape_product_info(),
                "recommendations": self.__scrape_suggested_products(),
                #"carousels": self.__scrape_raw_carousel_data()
            }

    def run(self, url):

        parsed = urlparse(url)

        if parsed.scheme in ["http", "https"]:
            self.driver.get(url)

        elif parsed.path == "homepage":
            self.driver.get("https://www.amazon.com/")

        elif parsed.path == "search":
            self.driver.get(
                f"https://smile.amazon.com/s?k={quote_plus(parsed.query)}"
            )

        elif parsed.path == "search_in_category":
            elements = parsed.query.split(":")
            category = elements[0]
            search_query = elements[1]
            self.driver.get(
                f"https://smile.amazon.com/s?k={quote_plus(search_query)}&i={category}"
            )

        self.__force_page_contents_load()

        return self.get_data()