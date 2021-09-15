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
                try { data['img'] = d.querySelector('img')['src']; } catch(err) {}
                try { section.querySelector("h2 .sp_desktop_sponsored_label").remove() } catch(err) {}
                try { section.querySelector("h2 a").remove() } catch(err) {}
                try { data['section_title'] = section.querySelector("h2").innerText; } catch(err) {}
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

            function getCarouselCurrentContents(root) {
                return [...root.querySelectorAll(".a-carousel-card:not(.vse-video-card)")].map((d, i) => {
                    let data = getItemDetails(d)
                    data['index'] = i;
                    return data; 
                });
            }

            async function getContentsOfCarousel(root, previousFirst, step=0) {
                if(step > 10) {
                    return Promise.resolve([])
                }
                if(!root.offsetParent) {
                    console.log(root.offsetParent)
                    return Promise.resolve([])
                }
                return new Promise((resolve, reject) => {
                    let contents = getCarouselCurrentContents(root)
                    let firstVisible = parseFloat(root.querySelector(".a-carousel-firstvisibleitem").value)
                    firstVisible = firstVisible == "" ? 1 : parseInt(firstVisible)
                    if(firstVisible != 1 || step == 0) {
                        console.log('scrolling to', root)
                        root.scrollIntoView()
                        root.querySelector(".a-carousel-goto-nextpage").click()

                        let tries = 0;
                        let waitUntilReady = setInterval(function() {
                            //let isBusy = root.querySelector(".a-carousel").ariaBusy;
                            let isLoaded = root.querySelectorAll(".a-carousel-card-empty").length == 0;
                            //console.log("isBusy?", isBusy);
                            console.log("isLoaded?", isLoaded);
                            if (isLoaded) {
                                console.log("scraping carrousel", root);
                                clearInterval(waitUntilReady);
                                getContentsOfCarousel(root, firstVisible, step + 1)
                                    .then(nextPageContents => {
                                        resolve([...contents, ...nextPageContents]);
                                    })
                            } 
                            else if (tries > 10) {
                                
                                // Remove empty cards
                                console.log('Removed unload elements after considerable wait');
                                toRemove = root.querySelectorAll(".a-carousel-card-empty");

                                for (let item of toRemove) {
                                    item.remove();
                                }
                            }
                            else {
                                console.log("working");
                                tries += 1;
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
            });"""

            # time.sleep(2)
            # self.driver.execute_script(
            #     """
            #     window.scrollTo({
            #         top: document.body.scrollHeight,
            #         left: 0,
            #         behavior: 'smooth'
            #     });"""
            # )
            # time.sleep(1)
            # self.driver.execute_script(
            #     "document.querySelectorAll('.a-carousel-goto-nextpage').forEach(e => e.click())"
            # )
            # time.sleep(1)
            # self.driver.execute_script(
            #     "document.querySelectorAll('.a-carousel-goto-nextpage').forEach(e => e.click())"
            # )
            # time.sleep(1)
            # self.driver.execute_script(
            #     "document.querySelectorAll('.a-carousel-goto-nextpage').forEach(e => e.click())"
            # )
    # time.sleep(1)
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
            product_id = re.search(".*/dp/(\d+)/.*", url).group(1)
            return product_id


        def scrape_product_name(driver):
            return driver.find_element_by_css_selector("span#productTitle").text

        
        def scrape_product_authors(driver):
            product_authors = driver.find_elements_by_css_selector("a.authorNameLink")
            product_authors = [author.text for author in product_authors]
            return product_authors


        def scrape_product_prices(driver):
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
            return (dict(zip(formats, prices)))


        def scrape_product_description(driver):
            frame = self.driver.find_element_by_css_selector("#bookDesc_iframe")
            self.driver.switch_to.frame(frame) # We have to enter the iFrame
            desc = self.driver.find_elements_by_css_selector("#iframeContent > *")
            product_description = "\n".join([item.text for item in desc])
            self.driver.switch_to.default_content() # Leave iframe


        def scrape_product_details(driver):
            
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
                        print(string)
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