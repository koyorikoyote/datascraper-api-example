import logging
import time
from sqlalchemy.orm import Session

from src.schemas import (
    KeywordUpdate,
    SerpResponse,
    TokenInfo,
    SearchResult,
    SearchResultUpdate
)
from src.services.keyword import KeywordService
from src.services.selenium import SeleniumService
from src.utils.constants import StatusConst
from src.utils.utils import get_domain_url


class TempTestService(KeywordService):
    """
    A service for testing keyword operations without saving to the database.
    This is used for production testing without affecting the actual data.
    """
    
    # Store active sessions (session_id -> SeleniumService instance)
    active_sessions = {}
    
    def __init__(self, db: Session):
        super().__init__(db)
    
    def run_fetch_test(self, ids: list[int], token: TokenInfo) -> list[SerpResponse]:
        """
        Run fetch operation for testing without saving to database.
        This method is similar to run_fetch but skips database updates.
        """
        responses: list[SerpResponse] = []
        
        for keyword_id in ids:
            keyword_obj = self.keyword_repo.get(keyword_id)
            if not keyword_obj:
                continue
                
            logging.info(f"Processing test fetch for keyword {keyword_id}")
            
            result = self._process_keyword_for_fetch_test(keyword_id)
            if result:
                responses.append(result)

        return responses

    def _process_keyword_for_fetch_test(self, keyword_id: int) -> SerpResponse | None:
        """
        Process a keyword for fetch testing without saving to database.
        """
        keyword_obj = self.keyword_repo.get(keyword_id)

        if not keyword_obj or not keyword_obj.keyword:
            raise ValueError("Keyword not found")

        items = self.serp_service.fetch_top_100(keyword_obj.keyword)
        if not items:
            raise ValueError(f"Failed to fetch SERP for keyword={keyword_obj.keyword}")

        seen_links = set()
        filtered_items = []
        for idx, item in enumerate(items, start=1):
            link = item.get("link", "")
            if link and link not in seen_links:
                seen_links.add(link)
                filtered_items.append(
                    SearchResult(
                        title=item.get("title", ""),
                        link=link,
                        snippet=item.get("snippet", ""),
                        position=idx
                    )
                )

        # Skip database update
        # self.serp_repo.create_bulk_unique(keyword_obj.id, filtered_items)
        # self.keyword_repo.update(keyword_obj, KeywordUpdate(fetch_status=StatusConst.SUCCESS))

        return SerpResponse(
            keyword_id=keyword_obj.id,
            keyword=keyword_obj.keyword,
            results=filtered_items
        )
    
    def run_rank_test(self, ids: list[int], token: TokenInfo) -> list[dict]:
        """
        Run rank operation for testing without saving to database.
        This method is similar to run_rank but skips database updates.
        """
        score_setting = self.score_setting.list_settings()
        results = []
        
        with SeleniumService() as selenium_service:
            for keyword_id in ids:
                keyword_obj = self.keyword_repo.get(keyword_id)
                if not keyword_obj:
                    continue
                    
                logging.info(f"Processing test rank for keyword {keyword_id}")
                
                try:
                    # Process all SERP results for this keyword
                    serp_results = self.serp_repo.list(keyword_id)
                    keyword_results = []
                    
                    for serp in serp_results:
                        try:
                            # Skip database update
                            # self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.PROCESSING))
                            
                            domain_url = get_domain_url(serp.link)
                            link_list = [domain_url]
                            all_possible_links_list = selenium_service.get_all_possible_links(domain_url)
                            
                            link_gpt = self._get_links_gpt(all_possible_links_list, serp.id)
                            
                            if not link_gpt:
                                logging.warning("Failed to get links from GPT for serp_id %s", serp.id)
                                continue
                            
                            if link_gpt.about:
                                link_list.append(link_gpt.about)
                            if link_gpt.contact:
                                link_list.append(link_gpt.contact)
                            
                            logging.info("Gathering text content from links: %s", link_list)
                            text_content = self._gather_link_texts(selenium_service, link_list)
                            logging.info("Fetched text content: %d chars", len(text_content))
                            
                            rank_gpt = self._get_rank_gpt(text_content, serp.id)
                            
                            if rank_gpt is None:
                                logging.warning("Failed to get rank from GPT for serp_id %s", serp.id)
                                continue

                            computation = self._compute_weight(rank_gpt, domain_url, score_setting)
                            rank = self._determine_rank(computation.total_weight, score_setting)
                            
                            # Instead of updating the database, collect the results
                            serp_result = {
                                "serp_id": serp.id,
                                "link": serp.link,
                                "rank": rank,
                                "computation": computation.model_dump(),
                                "company_name": rank_gpt.company_name,
                                "domain_name": domain_url,
                                "phone_number": rank_gpt.phone_number,
                                "url_corporate_site": rank_gpt.url_corporate_site,
                                "url_service_site": rank_gpt.url_service_site,
                                "email_address": rank_gpt.email_address
                            }
                            keyword_results.append(serp_result)
                            
                        except Exception as e:
                            logging.warning("Exception processing serp %s: %s", serp.id, e)
                            continue
                    
                    results.append({
                        "keyword_id": keyword_id,
                        "keyword": keyword_obj.keyword,
                        "serp_results": keyword_results
                    })
                    
                except Exception as e:
                    logging.warning("Exception processing keyword %s: %s", keyword_id, e)
                    continue
                    
        return results
        return results
        
    def process_single_serp(self, serp_id: int, token: TokenInfo) -> dict:
        """
        Process a single SERP result and update the database.
        This method allows rerunning the processing of a specific SERP result.
        
        Args:
            serp_id: The ID of the SERP result to process
            token: The user's token information
            
        Returns:
            A dictionary with the processing results
        """
        # Get the SERP result
        serp = self.serp_repo.get(serp_id)
        if not serp:
            raise ValueError(f"SERP result with ID {serp_id} not found")
            
        # Get the keyword and user
        keyword_obj = self.keyword_repo.get(serp.keyword_id)
        if not keyword_obj:
            raise ValueError(f"Keyword with ID {serp.keyword_id} not found")
            
        user_obj = self.user_repo.get(keyword_obj.created_by_user_id)
        if not user_obj:
            raise ValueError(f"User with ID {keyword_obj.created_by_user_id} not found")
            
        # Get score settings
        score_setting = self.score_setting.list_settings()
        
        try:
            with SeleniumService() as selenium_service:
                # Mark SERP as processing
                self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.PROCESSING))
                
                # Process the SERP result
                domain_url = get_domain_url(serp.link)
                link_list = [domain_url]
                
                # Get all possible links
                logging.info(f"Getting all possible links for {domain_url}")
                all_possible_links_list = selenium_service.get_all_possible_links(domain_url)
                
                # Get links from GPT
                logging.info(f"Getting links from GPT for serp_id {serp_id}")
                link_gpt = self._get_links_gpt(all_possible_links_list, serp.id)
                
                if not link_gpt:
                    logging.warning(f"Failed to get links from GPT for serp_id {serp_id}")
                    self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
                    raise ValueError(f"Failed to get links from GPT for serp_id {serp_id}")
                
                # Add about and contact links if available
                if link_gpt.about:
                    link_list.append(link_gpt.about)
                if link_gpt.contact:
                    link_list.append(link_gpt.contact)
                
                # Get text content
                logging.info(f"Gathering text content from links: {link_list}")
                text_content = self._gather_link_texts(selenium_service, link_list)
                logging.info(f"Fetched text content: {len(text_content)} chars")
                
                if not text_content:
                    logging.warning(f"Failed to get text content for serp_id {serp_id}")
                    self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
                    raise ValueError(f"Failed to get text content for serp_id {serp_id}")
                
                # Get rank from GPT
                logging.info(f"Getting rank from GPT for serp_id {serp_id}")
                rank_gpt = self._get_rank_gpt(text_content, serp.id)
                
                if rank_gpt is None:
                    logging.warning(f"Failed to get rank from GPT for serp_id {serp_id}")
                    self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
                    raise ValueError(f"Failed to get rank from GPT for serp_id {serp_id}")
                
                # Compute weight and determine rank
                computation = self._compute_weight(rank_gpt, domain_url, score_setting)
                rank = self._determine_rank(computation.total_weight, score_setting)
                
                # Update the database
                updated_serp = self.serp_repo.update(
                    serp,
                    SearchResultUpdate(
                        rank=rank,
                        status=StatusConst.SUCCESS,
                        **computation.model_dump(),
                        company_name=rank_gpt.company_name,
                        domain_name=domain_url,
                        contact_person=user_obj.full_name,
                        phone_number=rank_gpt.phone_number,
                        url_corporate_site=rank_gpt.url_corporate_site,
                        url_service_site=rank_gpt.url_service_site,
                        email_address=rank_gpt.email_address
                    )
                )
                
                # Return the results
                return {
                    "status": "success",
                    "serp_id": updated_serp.id,
                    "link": updated_serp.link,
                    "rank": updated_serp.rank,
                    "company_name": updated_serp.company_name,
                    "domain_name": updated_serp.domain_name,
                    "phone_number": updated_serp.phone_number,
                    "url_corporate_site": updated_serp.url_corporate_site,
                    "url_service_site": updated_serp.url_service_site,
                    "email_address": updated_serp.email_address,
                    "links": {
                        "all_links_count": len(all_possible_links_list),
                        "about": link_gpt.about,
                        "contact": link_gpt.contact
                    },
                    "text_content_length": len(text_content)
                }
                
        except Exception as e:
            logging.error(f"Error processing SERP {serp_id}: {str(e)}")
            # Make sure the SERP is marked as failed
            self.serp_repo.update(serp, SearchResultUpdate(status=StatusConst.FAILED))
            raise
    
    def keep_session_alive(self, session_id: str, selenium_service: SeleniumService, duration_seconds: int = 3600):
        """
        Background task to keep the Selenium session alive for a specified duration.
        
        Args:
            session_id: The ID of the session to keep alive
            selenium_service: The SeleniumService instance
            duration_seconds: How long to keep the session alive (default: 3600 seconds = 1 hour)
        """
        try:
            logging.info(f"Starting background task to keep session {session_id} alive for {duration_seconds} seconds")
            
            # Sleep for the specified duration
            time.sleep(duration_seconds)
            
            logging.info(f"Background task completed for session {session_id}, cleaning up")
            
            # Clean up the session after the duration
            if session_id in self.active_sessions:
                selenium_service._cleanup(force=True)
                del self.active_sessions[session_id]
                logging.info(f"Session {session_id} cleaned up after {duration_seconds} seconds")
                
        except Exception as e:
            logging.error(f"Error in background task for session {session_id}: {e}")
            # Try to clean up on error
            if session_id in self.active_sessions:
                try:
                    selenium_service._cleanup(force=True)
                    del self.active_sessions[session_id]
                except:
                    pass
