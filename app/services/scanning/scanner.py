"""Website scanner service for SEO analysis"""
import asyncio
import re
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, urljoin
from datetime import datetime
import httpx
from bs4 import BeautifulSoup


class WebsiteScanner:
    """Scans websites and provides SEO analysis"""
    
    def __init__(self, timeout: int = 30, max_pages: int = 10):
        self.timeout = timeout
        self.max_pages = max_pages
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; SiloqBot/1.0; +https://siloq.ai)'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    async def scan_website(self, url: str, scan_type: str = 'full') -> Dict[str, Any]:
        """
        Scan a website and return comprehensive SEO analysis.
        
        Args:
            url: Website URL to scan
            scan_type: 'full', 'quick', or 'technical'
        
        Returns:
            Dictionary with scan results including scores and recommendations
        """
        start_time = datetime.now()
        parsed_url = urlparse(url)
        domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        results = {
            'url': url,
            'domain': domain,
            'scan_type': scan_type,
            'status': 'processing',
            'pages_crawled': 0,
            'technical_score': 0.0,
            'content_score': 0.0,
            'structure_score': 0.0,
            'performance_score': 0.0,
            'seo_score': 0.0,
            'overall_score': 0.0,
            'technical_details': {},
            'content_details': {},
            'structure_details': {},
            'performance_details': {},
            'seo_details': {},
            'recommendations': [],
        }
        
        try:
            # Fetch homepage
            response = await self.client.get(url)
            response.raise_for_status()
            
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            results['pages_crawled'] = 1
            
            # Perform analysis
            technical_results = await self._analyze_technical(soup, response, url)
            content_results = await self._analyze_content(soup, url)
            structure_results = await self._analyze_structure(soup, url)
            performance_results = await self._analyze_performance(response, html)
            seo_results = await self._analyze_seo(soup, url)
            
            # Calculate scores
            results['technical_score'] = technical_results['score']
            results['content_score'] = content_results['score']
            results['structure_score'] = structure_results['score']
            results['performance_score'] = performance_results['score']
            results['seo_score'] = seo_results['score']
            
            # Calculate overall score (weighted average)
            weights = {
                'technical': 0.25,
                'content': 0.20,
                'structure': 0.20,
                'performance': 0.20,
                'seo': 0.15
            }
            
            results['overall_score'] = (
                technical_results['score'] * weights['technical'] +
                content_results['score'] * weights['content'] +
                structure_results['score'] * weights['structure'] +
                performance_results['score'] * weights['performance'] +
                seo_results['score'] * weights['seo']
            )
            
            # Determine grade
            results['grade'] = self._calculate_grade(results['overall_score'])
            
            # Store detailed results
            results['technical_details'] = technical_results['details']
            results['content_details'] = content_results['details']
            results['structure_details'] = structure_results['details']
            results['performance_details'] = performance_results['details']
            results['seo_details'] = seo_results['details']
            
            # Generate recommendations
            results['recommendations'] = self._generate_recommendations(results)
            
            # Calculate duration
            duration = (datetime.now() - start_time).total_seconds()
            results['scan_duration_seconds'] = int(duration)
            results['status'] = 'completed'
            
        except Exception as e:
            results['status'] = 'failed'
            results['error_message'] = str(e)
            results['scan_duration_seconds'] = int((datetime.now() - start_time).total_seconds())
        
        return results
    
    async def _analyze_technical(self, soup: BeautifulSoup, response: httpx.Response, url: str) -> Dict[str, Any]:
        """Analyze technical SEO factors"""
        score = 100.0
        details = {
            'has_doctype': False,
            'has_lang': False,
            'has_charset': False,
            'has_viewport': False,
            'has_robots_meta': False,
            'has_canonical': False,
            'has_sitemap': False,
            'has_robots_txt': False,
            'is_https': False,
            'has_favicon': False,
            'issues': [],
        }
        
        # Check doctype
        if soup.contents and hasattr(soup.contents[0], 'name'):
            details['has_doctype'] = True
        else:
            score -= 10
            details['issues'].append('Missing HTML5 doctype')
        
        # Check lang attribute
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            details['has_lang'] = True
        else:
            score -= 5
            details['issues'].append('Missing lang attribute on <html> tag')
        
        # Check charset
        charset = soup.find('meta', {'charset': True})
        if charset:
            details['has_charset'] = True
        else:
            score -= 5
            details['issues'].append('Missing charset meta tag')
        
        # Check viewport
        viewport = soup.find('meta', {'name': 'viewport'})
        if viewport:
            details['has_viewport'] = True
        else:
            score -= 10
            details['issues'].append('Missing viewport meta tag (mobile optimization)')
        
        # Check robots meta
        robots = soup.find('meta', {'name': 'robots'})
        if robots:
            details['has_robots_meta'] = True
        
        # Check canonical
        canonical = soup.find('link', {'rel': 'canonical'})
        if canonical:
            details['has_canonical'] = True
        else:
            score -= 10
            details['issues'].append('Missing canonical link tag')
        
        # Check HTTPS
        if url.startswith('https://'):
            details['is_https'] = True
        else:
            score -= 15
            details['issues'].append('Not using HTTPS (security and SEO issue)')
        
        # Check favicon
        favicon = soup.find('link', {'rel': lambda x: x and ('icon' in x.lower() or 'shortcut' in x.lower())})
        if favicon:
            details['has_favicon'] = True
        else:
            score -= 5
            details['issues'].append('Missing favicon')
        
        # Check robots.txt (async check)
        try:
            robots_url = urljoin(url, '/robots.txt')
            robots_response = await self.client.get(robots_url, timeout=5)
            if robots_response.status_code == 200:
                details['has_robots_txt'] = True
            else:
                score -= 5
                details['issues'].append('robots.txt not accessible')
        except:
            score -= 5
            details['issues'].append('robots.txt not found or inaccessible')
        
        # Check sitemap (in robots.txt or meta)
        sitemap = soup.find('link', {'rel': 'sitemap'})
        if sitemap:
            details['has_sitemap'] = True
        else:
            score -= 5
            details['issues'].append('Sitemap not declared')
        
        score = max(0.0, score)
        
        return {
            'score': score,
            'details': details
        }
    
    async def _analyze_content(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Analyze content quality"""
        score = 100.0
        details = {
            'has_title': False,
            'has_meta_description': False,
            'has_h1': False,
            'has_heading_structure': False,
            'has_alt_text': False,
            'content_length': 0,
            'word_count': 0,
            'issues': [],
        }
        
        # Check title
        title = soup.find('title')
        if title and title.text.strip():
            title_text = title.text.strip()
            details['has_title'] = True
            details['title'] = title_text
            if len(title_text) < 30:
                score -= 10
                details['issues'].append('Title tag too short (should be 30-60 characters)')
            elif len(title_text) > 60:
                score -= 5
                details['issues'].append('Title tag too long (should be 30-60 characters)')
        else:
            score -= 20
            details['issues'].append('Missing title tag')
        
        # Check meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            desc_text = meta_desc.get('content', '').strip()
            details['has_meta_description'] = True
            details['meta_description'] = desc_text
            if len(desc_text) < 120:
                score -= 10
                details['issues'].append('Meta description too short (should be 120-160 characters)')
            elif len(desc_text) > 160:
                score -= 5
                details['issues'].append('Meta description too long (should be 120-160 characters)')
        else:
            score -= 15
            details['issues'].append('Missing meta description')
        
        # Check H1
        h1 = soup.find('h1')
        if h1 and h1.text.strip():
            details['has_h1'] = True
            details['h1'] = h1.text.strip()
            h1_count = len(soup.find_all('h1'))
            if h1_count > 1:
                score -= 10
                details['issues'].append(f'Multiple H1 tags found ({h1_count}) - should have only one')
        else:
            score -= 15
            details['issues'].append('Missing H1 tag')
        
        # Check heading structure
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        if len(headings) > 0:
            details['has_heading_structure'] = True
            details['heading_count'] = len(headings)
            # Check for proper hierarchy
            prev_level = 0
            for heading in headings[:10]:  # Check first 10 headings
                level = int(heading.name[1])
                if level > prev_level + 1:
                    score -= 5
                    details['issues'].append('Heading hierarchy skipped (e.g., H1 to H3)')
                    break
                prev_level = level
        else:
            score -= 10
            details['issues'].append('No heading structure found')
        
        # Check alt text on images
        images = soup.find_all('img')
        images_with_alt = sum(1 for img in images if img.get('alt') is not None)
        total_images = len(images)
        if total_images > 0:
            alt_percentage = (images_with_alt / total_images) * 100
            details['has_alt_text'] = alt_percentage > 80
            details['alt_text_coverage'] = alt_percentage
            if alt_percentage < 80:
                score -= (100 - alt_percentage) * 0.2
                details['issues'].append(f'Only {alt_percentage:.0f}% of images have alt text')
        else:
            details['has_alt_text'] = True  # No images, so no issue
        
        # Check content length
        body = soup.find('body')
        if body:
            text = body.get_text(separator=' ', strip=True)
            details['content_length'] = len(text)
            details['word_count'] = len(text.split())
            if details['word_count'] < 300:
                score -= 15
                details['issues'].append('Content too short (should be at least 300 words)')
        
        score = max(0.0, score)
        
        return {
            'score': score,
            'details': details
        }
    
    async def _analyze_structure(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Analyze site structure"""
        score = 100.0
        details = {
            'has_navigation': False,
            'has_footer': False,
            'has_schema': False,
            'link_count': 0,
            'internal_links': 0,
            'external_links': 0,
            'issues': [],
        }
        
        # Check navigation
        nav = soup.find('nav') or soup.find('div', {'class': lambda x: x and 'nav' in x.lower()})
        if nav:
            details['has_navigation'] = True
        else:
            score -= 10
            details['issues'].append('No navigation structure found')
        
        # Check footer
        footer = soup.find('footer')
        if footer:
            details['has_footer'] = True
        else:
            score -= 5
            details['issues'].append('No footer found')
        
        # Check schema markup
        schemas = soup.find_all('script', {'type': 'application/ld+json'})
        if schemas:
            details['has_schema'] = True
            details['schema_count'] = len(schemas)
        else:
            score -= 15
            details['issues'].append('No structured data (JSON-LD schema) found')
        
        # Analyze links
        links = soup.find_all('a', href=True)
        details['link_count'] = len(links)
        parsed_base = urlparse(url)
        
        for link in links:
            href = link.get('href', '')
            if href.startswith('http'):
                parsed_link = urlparse(href)
                if parsed_link.netloc == parsed_base.netloc:
                    details['internal_links'] += 1
                else:
                    details['external_links'] += 1
            elif href.startswith('/') or not href.startswith('#'):
                details['internal_links'] += 1
        
        if details['internal_links'] < 5:
            score -= 10
            details['issues'].append('Very few internal links found')
        
        score = max(0.0, score)
        
        return {
            'score': score,
            'details': details
        }
    
    async def _analyze_performance(self, response: httpx.Response, html: str) -> Dict[str, Any]:
        """Analyze performance metrics"""
        score = 100.0
        details = {
            'response_time_ms': 0,
            'page_size_kb': 0,
            'has_compression': False,
            'issues': [],
        }
        
        # Response time (approximate)
        details['response_time_ms'] = int(response.elapsed.total_seconds() * 1000)
        if details['response_time_ms'] > 3000:
            score -= 20
            details['issues'].append(f'Slow response time: {details["response_time_ms"]}ms (should be < 3s)')
        elif details['response_time_ms'] > 2000:
            score -= 10
            details['issues'].append(f'Response time could be improved: {details["response_time_ms"]}ms')
        
        # Page size
        page_size = len(html.encode('utf-8'))
        details['page_size_kb'] = round(page_size / 1024, 2)
        if details['page_size_kb'] > 2000:
            score -= 15
            details['issues'].append(f'Page size too large: {details["page_size_kb"]}KB (should be < 2MB)')
        elif details['page_size_kb'] > 1000:
            score -= 5
            details['issues'].append(f'Page size could be optimized: {details["page_size_kb"]}KB')
        
        # Check compression
        if 'content-encoding' in response.headers:
            details['has_compression'] = True
        else:
            score -= 5
            details['issues'].append('Response not compressed (enable gzip/brotli)')
        
        score = max(0.0, score)
        
        return {
            'score': score,
            'details': details
        }
    
    async def _analyze_seo(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Analyze SEO-specific factors"""
        score = 100.0
        details = {
            'has_open_graph': False,
            'has_twitter_card': False,
            'has_meta_keywords': False,
            'has_robots_noindex': False,
            'issues': [],
        }
        
        # Check Open Graph
        og_tags = soup.find_all('meta', {'property': lambda x: x and x.startswith('og:')})
        if og_tags:
            details['has_open_graph'] = True
            details['og_tags_count'] = len(og_tags)
        else:
            score -= 10
            details['issues'].append('Missing Open Graph tags (social sharing)')
        
        # Check Twitter Card
        twitter_tags = soup.find_all('meta', {'name': lambda x: x and x.startswith('twitter:')})
        if twitter_tags:
            details['has_twitter_card'] = True
        else:
            score -= 5
            details['issues'].append('Missing Twitter Card tags')
        
        # Check for noindex (bad for SEO)
        robots = soup.find('meta', {'name': 'robots'})
        if robots and robots.get('content'):
            content = robots.get('content', '').lower()
            if 'noindex' in content:
                details['has_robots_noindex'] = True
                score -= 50
                details['issues'].append('Page has noindex directive (will not be indexed by search engines)')
        
        score = max(0.0, score)
        
        return {
            'score': score,
            'details': details
        }
    
    def _calculate_grade(self, score: float) -> str:
        """Calculate letter grade from score"""
        if score >= 97:
            return 'A+'
        elif score >= 93:
            return 'A'
        elif score >= 87:
            return 'B+'
        elif score >= 83:
            return 'B'
        elif score >= 77:
            return 'C+'
        elif score >= 73:
            return 'C'
        elif score >= 67:
            return 'D+'
        elif score >= 63:
            return 'D'
        else:
            return 'F'
    
    def _generate_recommendations(self, results: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate actionable recommendations based on scan results"""
        recommendations = []
        
        # Technical recommendations
        tech_issues = results.get('technical_details', {}).get('issues', [])
        for issue in tech_issues[:3]:  # Top 3 issues
            recommendations.append({
                'category': 'Technical SEO',
                'priority': 'high' if 'HTTPS' in issue or 'doctype' in issue.lower() else 'medium',
                'issue': issue,
                'action': self._get_recommendation_action(issue)
            })
        
        # Content recommendations
        content_issues = results.get('content_details', {}).get('issues', [])
        for issue in content_issues[:3]:
            recommendations.append({
                'category': 'Content',
                'priority': 'high' if 'title' in issue.lower() or 'H1' in issue else 'medium',
                'issue': issue,
                'action': self._get_recommendation_action(issue)
            })
        
        # Structure recommendations
        structure_issues = results.get('structure_details', {}).get('issues', [])
        for issue in structure_issues[:2]:
            recommendations.append({
                'category': 'Structure',
                'priority': 'medium',
                'issue': issue,
                'action': self._get_recommendation_action(issue)
            })
        
        # Performance recommendations
        perf_issues = results.get('performance_details', {}).get('issues', [])
        for issue in perf_issues[:2]:
            recommendations.append({
                'category': 'Performance',
                'priority': 'high' if 'slow' in issue.lower() else 'medium',
                'issue': issue,
                'action': self._get_recommendation_action(issue)
            })
        
        return recommendations[:10]  # Limit to top 10
    
    def _get_recommendation_action(self, issue: str) -> str:
        """Get actionable recommendation for an issue"""
        issue_lower = issue.lower()
        
        if 'https' in issue_lower:
            return 'Enable SSL/TLS certificate and redirect all HTTP traffic to HTTPS'
        elif 'title' in issue_lower:
            return 'Optimize title tag to be 30-60 characters and include primary keyword'
        elif 'meta description' in issue_lower:
            return 'Add or optimize meta description to 120-160 characters with compelling copy'
        elif 'h1' in issue_lower:
            return 'Ensure exactly one H1 tag per page with primary keyword'
        elif 'alt text' in issue_lower:
            return 'Add descriptive alt text to all images for accessibility and SEO'
        elif 'canonical' in issue_lower:
            return 'Add canonical link tag to prevent duplicate content issues'
        elif 'schema' in issue_lower or 'structured data' in issue_lower:
            return 'Implement JSON-LD structured data for better search visibility'
        elif 'viewport' in issue_lower:
            return 'Add viewport meta tag for mobile optimization'
        elif 'slow' in issue_lower or 'response time' in issue_lower:
            return 'Optimize server response time, enable caching, and minimize HTTP requests'
        elif 'page size' in issue_lower:
            return 'Compress images, minify CSS/JS, and enable gzip compression'
        elif 'noindex' in issue_lower:
            return 'Remove noindex directive if you want this page indexed by search engines'
        else:
            return 'Review and address this issue to improve SEO performance'
