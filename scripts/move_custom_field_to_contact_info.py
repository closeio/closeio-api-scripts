#!/usr/bin/env python
import click
from closeio_api import APIError, Client as CloseIO_API


@click.command()
@click.option('-k', '--api-key', required=True, help='API key')
@click.option(
    '--confirmed',
    is_flag=True,
    help='Without this flag, the script will do a dry run without actually updating any data.',
)
@click.option(
    '--use_existing_contact',
    is_flag=True,
    help='Append the phone number from a custom field to an existing contact. If this flag is not used, a new contact will be created.',
)
@click.option(
    '--new_contact_name',
    default='',
    help="If --use_existing_contact flag was not set, or if a lead doesn't contain any contacts, this is the name of the contact that will be created.",
)
@click.option(
    '--phones_custom_field',
    default='all phones',
    help='Name of the custom field containing phones that should be moved into a contact.',
)
@click.option(
    '--emails_custom_field',
    default='all emails',
    help='Name of the custom field containing emails that should be moved into a contact.',
)
@click.option(
    '--title_custom_field',
    default='contact title',
    help='Name of the custom field containing a contact\'s title.',
)
def run(
    api_key,
    confirmed,
    use_existing_contact=False,
    new_contact_name='',
    phones_custom_field='all phones',
    emails_custom_field='all emails',
    title_custom_field='contact title',
):
    """
    After an import from a different CRM, for all leads, move emails and phones that were put in
    in a lead custom field to the lead's first contact (if--use_existing_contact flag was used)
    or create a new contact.
    """

    print(f'confirmed: {confirmed}')
    print(f'phones_custom_field: {phones_custom_field}')
    print(f'emails_custom_field: {emails_custom_field}')
    print(f'title_custom_field: {title_custom_field}')
    print(f'use_existing_contact: {use_existing_contact}')

    api = CloseIO_API(api_key)
    has_more = True
    offset = 0

    while has_more:

        # Get a page of leads
        resp = api.get(
            'lead',
            params={
                'query': '"custom.Source CRM":* not "custom.Migration completed":* sort:created',
                '_skip': offset,
                '_fields': 'id,display_name,name,contacts,custom',
            },
        )
        leads = resp['data']

        for lead in leads:
            contacts = lead['contacts']
            custom = lead['custom']

            company_emails = custom.get(emails_custom_field, '')
            company_phones = custom.get(phones_custom_field, '')
            contact_title = custom.get(title_custom_field, '')

            if not company_phones and not company_emails and not contact_title:
                continue

            if company_emails:
                if company_emails.startswith('["'):
                    company_emails = company_emails[2:-2].split('", "')
                else:
                    company_emails = [company_emails]

            if company_phones:
                if company_phones.startswith('["'):
                    company_phones = company_phones[2:-2].split('", "')
                else:
                    company_phones = [company_phones]

            if contacts and use_existing_contact:
                contact = contacts[0]
            else:
                contact = {'lead_id': lead['id'], 'phones': [], 'emails': []}
                if new_contact_name:
                    contact['name'] = new_contact_name

            for pn in company_phones:
                contact['phones'].append({'type': 'office', 'phone': pn})
            for e in company_emails:
                contact['emails'].append({'type': 'office', 'email': e})
            if contact_title:
                contact['title'] = contact_title

            print('Lead:', lead['id'], lead['name'].encode('utf8'))
            print(
                f'Emails: {custom.get(emails_custom_field)} => {company_emails}'
            )
            print(
                f'Phones: {custom.get(phones_custom_field)} => {company_phones}'
            )
            print(
                f'Title: {custom.get(title_custom_field)} => {contact_title}'
            )

            try:
                if contact.get('id'):
                    print('Updating an existing contact', contact['id'])
                    if confirmed:
                        api.put(
                            'contact/%s' % contact['id'],
                            data={
                                'phones': contact['phones'],
                                'emails': contact['emails'],
                            },
                        )
                else:
                    print('Creating a new contact')
                    if confirmed:
                        api.post('contact', data=contact)
                print('Payload:', contact)
                if confirmed:
                    api.put(
                        'lead/%s' % lead['id'],
                        data={'custom.Migration completed': 'Yes'},
                    )
            except APIError as e:
                print(str(e))
                print('Payload:', contact)
                if confirmed:
                    api.put(
                        'lead/%s' % lead['id'],
                        data={'custom.Migration completed': 'skipped'},
                    )

            print()

        if not confirmed:
            # If we don't actually update the "Migration completed" custom field,
            # we need to paginate
            offset += len(leads)

        has_more = resp['has_more']

    print('Done')


if __name__ == '__main__':
    run()
