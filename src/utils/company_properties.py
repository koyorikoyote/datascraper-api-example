COMPANY_PROPERTIES = [
  {
    "name": "activity_date",
    "label": "アクティビティー日",
    "groupName": "companyinformation",
    "type": "datetime",
    "fieldType": "date",
    "formField": True
  },
  {
    "name": "next_form",
    "label": "次回の問い合わせ送付日",
    "groupName": "companyinformation",
    "type": "date",
    "fieldType": "date",
    "formField": True
  },
  {
    "name": "rank",
    "label": "リストランク",
    "groupName": "companyinformation",
    "type": "enumeration",
    "fieldType": "select",
    "formField": True,
    "options": [
      {
        "label": "A",
        "value": "A",
        "displayOrder": 0,
        "hidden": False
      },
      {
        "label": "B",
        "value": "B",
        "displayOrder": 1,
        "hidden": False
      },
      {
        "label": "C",
        "value": "C",
        "displayOrder": 2,
        "hidden": False
      },
      {
        "label": "D",
        "value": "D",
        "displayOrder": 3,
        "hidden": False
      },
      {
        "label": "E",
        "value": "E",
        "displayOrder": 4,
        "hidden": False
      }
    ]
  },
  {
    "name": "corporate_contact_url",
    "label": "問い合わせURL（コーポレートサイト）",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": True
  },
  {
    "name": "service_contact_url",
    "label": "問い合わせURL（サービスサイト）",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": True
  },
  {
    "name": "mail",
    "label": "問い合わせメールアドレス",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": True
  },
  {
    "name": "memo",
    "label": "メモ",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "textarea",
    "formField": True
  },
  {
    "name": "status",
    "label": "問合せ実行状況",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": False,
    "description": "システム用: ^pending$|^processing$|^failed$|^success$"
  },
  {
    "name": "batch_id",
    "label": "実行ID",
    "groupName": "companyinformation",
    "type": "number",
    "fieldType": "number",
    "formField": False,
    "description": "「システム用の一意な整数識別子」"
  },
  {
    "name": "title",
    "label": "タイトル",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": True
  },
  {
    "name": "service_price",
    "label": "サービス単価",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": True
  },
  {
    "name": "service_volume",
    "label": "KW検索ボリューム",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": True
  },
  {
    "name": "site_size",
    "label": "サイト規模",
    "groupName": "companyinformation",
    "type": "string",
    "fieldType": "text",
    "formField": True
  }
]
