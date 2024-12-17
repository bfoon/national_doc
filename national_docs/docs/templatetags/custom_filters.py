from django import template

register = template.Library()

@register.filter(name='masked_phone')
def masked_phone(value):
    if value and len(value) >= 2:
        return f"{'*' * (len(value) - 2)}{value[-2:]}"
    return value

@register.filter(name='masked_email')
def masked_email(value):
    if value and '@' in value:
        user, domain = value.split('@')
        masked_user = f"{user[0]}{'*' * (len(user) - 2)}{user[-1]}"
        masked_domain = f"{domain[0]}{'*' * (len(domain) - 3)}{domain[-2:]}"
        return f"{masked_user}@{masked_domain}"
    return value
