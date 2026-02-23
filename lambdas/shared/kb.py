"""Knowledge Base data access layer for CommandBridge.

Handles CRUD operations against the KB DynamoDB table with versioning.
Each article has id (hash key) + version (range key). The sparse GSI
'latest-index' contains only items where is_latest="true".
"""

import boto3
import os
import time
import re

from shared.pagination import decimal_to_int, encode_cursor, decode_cursor

_table_name = os.environ.get('KB_TABLE', 'commandbridge-dev-kb')
_dynamodb = boto3.resource('dynamodb')
_table = _dynamodb.Table(_table_name)

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


def _article_response(item):
    """Format a DynamoDB item as an article response dict."""
    cleaned = {k: v for k, v in item.items() if not k.endswith('_lower')}
    return decimal_to_int(cleaned)


def slugify(title):
    """Convert a title to a URL-safe slug."""
    slug = title.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s_]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def list_articles(search=None, service=None, category=None, cursor=None, limit=DEFAULT_LIMIT):
    """List latest articles, optionally filtered by search, service, or category.

    Uses the latest-index GSI for efficient pagination.
    """
    limit = min(int(limit), MAX_LIMIT)
    exclusive_start = decode_cursor(cursor)

    if service:
        # Use service-index GSI
        kwargs = {
            'IndexName': 'service-index',
            'KeyConditionExpression': boto3.dynamodb.conditions.Key('service').eq(service),
            'ScanIndexForward': False,
            'Limit': limit,
            'FilterExpression': boto3.dynamodb.conditions.Attr('is_latest').eq('true'),
        }
    else:
        # Use latest-index GSI
        kwargs = {
            'IndexName': 'latest-index',
            'KeyConditionExpression': boto3.dynamodb.conditions.Key('is_latest').eq('true'),
            'ScanIndexForward': False,
            'Limit': limit,
        }

    if exclusive_start:
        kwargs['ExclusiveStartKey'] = exclusive_start

    if category:
        cat_filter = boto3.dynamodb.conditions.Attr('category').eq(category)
        if 'FilterExpression' in kwargs:
            kwargs['FilterExpression'] = kwargs['FilterExpression'] & cat_filter
        else:
            kwargs['FilterExpression'] = cat_filter

    if search:
        search_lower = search.lower()
        filter_expr = (
            boto3.dynamodb.conditions.Attr('title_lower').contains(search_lower) |
            boto3.dynamodb.conditions.Attr('service_lower').contains(search_lower) |
            boto3.dynamodb.conditions.Attr('owner_lower').contains(search_lower) |
            boto3.dynamodb.conditions.Attr('tags_lower').contains(search_lower)
        )
        if 'FilterExpression' in kwargs:
            kwargs['FilterExpression'] = kwargs['FilterExpression'] & filter_expr
        else:
            kwargs['FilterExpression'] = filter_expr

    result = _table.query(**kwargs)

    # Strip content and internal fields from list response
    articles = []
    for item in result.get('Items', []):
        cleaned = {k: v for k, v in item.items() if not k.endswith('_lower')}
        article = decimal_to_int(cleaned)
        article.pop('content', None)
        articles.append(article)

    return {
        'articles': articles,
        'cursor': encode_cursor(result.get('LastEvaluatedKey')),
    }


def get_article(article_id, version=None):
    """Get a single article by ID. Returns latest version unless version specified."""
    if version is not None:
        result = _table.get_item(Key={'id': article_id, 'version': int(version)})
        item = result.get('Item')
        if item:
            return _article_response(item)
        return None

    # Query all versions descending, filter for is_latest without Limit
    # (Limit applies before FilterExpression, so Limit=1 can miss during concurrent updates)
    result = _table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('id').eq(article_id),
        ScanIndexForward=False,
        FilterExpression=boto3.dynamodb.conditions.Attr('is_latest').eq('true'),
    )
    items = result.get('Items', [])
    if not items:
        return None
    return _article_response(items[0])


def get_versions(article_id):
    """Get all versions of an article (metadata only, no content)."""
    result = _table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('id').eq(article_id),
        ScanIndexForward=False,
    )
    versions = []
    for item in result.get('Items', []):
        v = decimal_to_int(item)
        v.pop('content', None)
        versions.append(v)
    return versions


def create_article(title, service, owner, tags, content, user_email, category=''):
    """Create a new article. Returns the created article."""
    article_id = slugify(title)
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    item = {
        'id': article_id,
        'version': 1,
        'title': title,
        'slug': article_id,
        'owner': owner,
        'tags': tags or [],
        'last_reviewed': now[:10],
        'content': content,
        'created_at': now,
        'created_by': user_email,
        'updated_at': now,
        'updated_by': user_email,
        'is_latest': 'true',
        'title_lower': title.lower(),
        'owner_lower': owner.lower(),
        'tags_lower': ','.join(t.lower() for t in (tags or [])),
    }
    # DynamoDB GSI keys cannot be empty strings — only include when non-empty
    if service:
        item['service'] = service
        item['service_lower'] = service.lower()
    if category:
        item['category'] = category

    # Check if article with this ID already exists
    existing = get_article(article_id)
    if existing:
        return None  # Conflict

    _table.put_item(Item=item)
    return _article_response(item)


def update_article(article_id, title, service, owner, tags, content, user_email, category=None):
    """Update an article by creating a new version."""
    current = get_article(article_id)
    if not current:
        return None

    new_version = current['version'] + 1
    now = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())

    # Remove is_latest from the current version (drops it from sparse GSI)
    _table.update_item(
        Key={'id': article_id, 'version': current['version']},
        UpdateExpression='REMOVE is_latest',
    )

    # Create new version
    final_title = title or current['title']
    final_service = service or current.get('service', '')
    final_owner = owner or current.get('owner', '')
    final_category = category if category is not None else current.get('category', '')
    final_tags = tags if tags is not None else current.get('tags', [])
    item = {
        'id': article_id,
        'version': new_version,
        'title': final_title,
        'slug': article_id,
        'owner': final_owner,
        'tags': final_tags,
        'last_reviewed': now[:10],
        'content': content if content is not None else current['content'],
        'created_at': current['created_at'],
        'created_by': current['created_by'],
        'updated_at': now,
        'updated_by': user_email,
        'is_latest': 'true',
        'title_lower': final_title.lower(),
        'owner_lower': final_owner.lower(),
        'tags_lower': ','.join(t.lower() for t in final_tags),
    }
    # DynamoDB GSI keys cannot be empty strings — only include when non-empty
    if final_service:
        item['service'] = final_service
        item['service_lower'] = final_service.lower()
    if final_category:
        item['category'] = final_category

    _table.put_item(Item=item)
    return _article_response(item)


def delete_article(article_id):
    """Delete all versions of an article."""
    # Get all versions
    versions = get_versions(article_id)
    if not versions:
        return False

    with _table.batch_writer() as batch:
        for v in versions:
            batch.delete_item(Key={'id': article_id, 'version': v['version']})

    return True


def restore_version(article_id, target_version, user_email):
    """Restore an old version as the new latest."""
    old = get_article(article_id, version=target_version)
    if not old:
        return None

    return update_article(
        article_id,
        title=old['title'],
        service=old['service'],
        owner=old['owner'],
        tags=old.get('tags', []),
        content=old['content'],
        user_email=user_email,
        category=old.get('category', ''),
    )
