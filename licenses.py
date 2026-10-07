"""Installation-owner utility. Keep this tool on the owner's computer."""
import argparse, datetime
import auth

def date_label(value):
    return datetime.datetime.fromtimestamp(value).strftime('%d/%m/%Y %H:%M') if value else 'Sem prazo'

def status_label(row):
    if not row['active']:return 'Desativada'
    if row['expires'] is not None and row['expires']<=datetime.datetime.now().timestamp():return 'Expirada'
    return 'Ativa'

def issue(email,days):
    result=auth.issue_license(email,days)
    print('\nCHAVE DE ATIVAÇÃO (copie agora; ela não é armazenada em texto):\n'+result['key'])
    print('ID: '+result['id'])
    print('E-mail: '+(result['email'] or 'Primeira conta que ativar'))
    print('Validade: '+date_label(result['expires']))

def main():
    parser=argparse.ArgumentParser(description='Gerenciar licenças desta instalação do aprova.ai')
    parser.add_argument('action',nargs='?',choices=['emitir','listar','revogar'])
    parser.add_argument('--email',default='')
    parser.add_argument('--dias',type=int)
    parser.add_argument('--id',default='')
    args=parser.parse_args()
    if args.action:
        if args.action=='emitir':issue(args.email,args.dias)
        elif args.action=='revogar':auth.revoke_license(args.id);print('Licença desativada.')
        else:
            for row in auth.list_licenses():print(row['id'], status_label(row),row['activated_email'] or row['email'] or 'Não ativada',date_label(row['expires']))
        return
    print('APROVA.AI — LICENÇAS DESTA INSTALAÇÃO\n1. Gerar licença\n2. Listar licenças\n3. Desativar licença')
    choice=input('Escolha: ').strip()
    if choice=='1':
        email=input('E-mail do aluno (opcional): ').strip()
        value=input('Validade em dias (Enter = sem prazo): ').strip()
        issue(email,int(value) if value else None)
    elif choice=='2':
        for row in auth.list_licenses():print(row['id'], status_label(row),row['activated_email'] or row['email'] or 'Não ativada',date_label(row['expires']))
    elif choice=='3':
        auth.revoke_license(input('ID ou chave completa: '));print('Licença desativada.')
    else:raise ValueError('Opção inválida.')

if __name__=='__main__':
    try:main()
    except Exception as error:print('Não foi possível concluir:',error)
    input('\nPressione Enter para fechar...')
