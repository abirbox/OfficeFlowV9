import EntityCrudPage from './EntityCrudPage';
import ClientPortalLoginDialog from './ClientPortalLoginDialog';

export const ClientsPage = () => (
  <EntityCrudPage
    title="Clients" endpoint="/dispatch/clients" permBase="dispatch.clients"
    rowActions={(row) => <ClientPortalLoginDialog client={row} />}
    columns={[{ key: 'logo_path', label: 'Logo', type: 'logo' }, { key: 'name', label: 'Name' }, { key: 'code', label: 'Code' }, { key: 'contact_person', label: 'Contact' }, { key: 'contact_number', label: 'Phone' }, { key: 'city', label: 'City' }]}
    fields={[
      { key: 'logo_path', label: 'Logo', type: 'logo' },
      { key: 'name', label: 'Name', required: true },
      { key: 'code', label: 'Code' },
      { key: 'accent_color', label: 'Brand Color (Invoice Accent)', type: 'color' },
      { key: 'contact_person', label: 'Contact Person' },
      { key: 'contact_number', label: 'Contact Number' },
      { key: 'email', label: 'Email' },
      { key: 'website', label: 'Website' },
      { key: 'address', label: 'Address' },
      { key: 'city', label: 'City' },
      { key: 'location', label: 'Location', required: true },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ]}
  />
);

export const VendorsPage = () => (
  <EntityCrudPage
    title="Vendors" endpoint="/dispatch/vendors" permBase="dispatch.vendors"
    columns={[{ key: 'logo_path', label: 'Logo', type: 'logo' }, { key: 'name', label: 'Name' }, { key: 'code', label: 'Code' }, { key: 'contact_person', label: 'Contact' }, { key: 'contact_number', label: 'Phone' }, { key: 'city', label: 'City' }]}
    fields={[
      { key: 'logo_path', label: 'Logo', type: 'logo' },
      { key: 'name', label: 'Name', required: true },
      { key: 'code', label: 'Code' },
      { key: 'client_ids', label: 'Linked Clients (which Clients this Vendor serves)', multi: 'clients' },
      { key: 'contact_person', label: 'Contact Person' },
      { key: 'contact_number', label: 'Contact Number' },
      { key: 'email', label: 'Email' },
      { key: 'website', label: 'Website' },
      { key: 'address', label: 'Address' },
      { key: 'city', label: 'City' },
      { key: 'location', label: 'Location' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ]}
  />
);

export const OfficersPage = () => (
  <EntityCrudPage
    title="Security Officers" endpoint="/dispatch/officers" permBase="dispatch.officers"
    columns={[
      { key: 'officer_code', label: 'Officer Code' },
      { key: 'name', label: 'Officer Name' },
      { key: 'client_name', label: 'Client' },
      { key: 'social_security_code', label: 'Social Security Code' },
      { key: 'type', label: 'Type' },
      { key: 'contact_number', label: 'Phone' },
      { key: 'email', label: 'Email' },
    ]}
    filters={[
      { key: 'client_id', label: 'Client', type: 'clients' },
      {
        key: 'type',
        label: 'Type',
        options: [
          { value: 'Armed', label: 'Armed' },
          { value: 'Unarmed', label: 'Unarmed' },
        ],
      },
      {
        key: 'status',
        label: 'Status',
        options: [
          { value: 'active', label: 'Active' },
          { value: 'inactive', label: 'Inactive' },
          { value: 'suspended', label: 'Suspended' },
          { value: 'terminated', label: 'Terminated' },
          { value: 'on_leave', label: 'On Leave' },
        ],
      },
    ]}
    fields={[
      { key: 'name', label: 'Name', required: true },
      { key: 'officer_code', label: 'Officer Code', readOnly: true },
      { key: 'contact_number', label: 'Contact Number', required: true },
      { key: 'alternate_contact_number', label: 'Alternate Number' },
      { key: 'social_security_code', label: 'Social Security Code' },
      { key: 'email', label: 'Email' },
      { key: 'client_id', label: 'Client', select: 'clients', required: true },
      {
        key: 'type',
        label: 'Type',
        options: [
          { value: 'Armed', label: 'Armed' },
          { value: 'Unarmed', label: 'Unarmed' },
        ],
        required: true
      },
      { key: 'address', label: 'Address' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ]}
    statuses={[
      { value: 'active', label: 'Active' },
      { value: 'inactive', label: 'Inactive' },
      { value: 'suspended', label: 'Suspended' },
      { value: 'terminated', label: 'Terminated' },
      { value: 'on_leave', label: 'On Leave' },
    ]}
  />
);

export const PostSitesPage = () => (
  <EntityCrudPage
    title="Post Sites" endpoint="/dispatch/post-sites" permBase="dispatch.post_sites"
    columns={[
      { key: 'post_pin', label: 'Post Pin' },
      { key: 'name', label: 'Name' },
      { key: 'type', label: 'Type' },
      { key: 'city', label: 'City' }
    ]}
    fields={[
      { key: 'post_pin', label: 'Post Site Pin', required: true },
      { key: 'name', label: 'Post Site Name', required: true },
      {
        key: 'type',
        label: 'Type',
        options: [
          { value: 'Armed', label: 'Armed' },
          { value: 'Unarmed', label: 'Unarmed' }
        ]
      },
      { key: 'location', label: 'Address' },
      { key: 'city', label: 'City' },
      { key: 'notes', label: 'Note', type: 'textarea' },
    ]}
  />
);
