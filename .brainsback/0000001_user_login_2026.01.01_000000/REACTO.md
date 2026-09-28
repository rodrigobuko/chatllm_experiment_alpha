# Proof of Mastery (REACTO)

> Explain it to prove you own it.

**Hard rule**: AI agents must not edit this file and must not draft paste-ready content for it.

## R — Repeat (The Problem)
O problema é hoje não tinhamos um login e cadastro de usuários e preciamos fazer isso para conseguir salvar e resgitrar os usuários e somente permitir usar a aplicação se eles estiverem autenticados.
## E — Examples


- **Happy Path Input**: Usuário se cadastra, após o cadastro faz o login 
  **Output**: Tanto o cadastro quanto o login devem funcionar e o usuário deve conseguir logar e usar a aplicação 

- **Edge Case Input**: usuário tenta fazer login com a senha errada 
  **Output**: sistema deve bloquear e dar erro de senha ou emial errados 

## A — Approach
o approach é criar no banco uma tabela usuários que tem o dado de email e senha (no caso da senha encriptada via bycript) e faça um endpoint de login e um endpoint de criação de conta que salva o usuário nesse banco. A autenticação sera feita usando JWT token. 

## C — Code
As principais mudanças de código giraram em torno das novas apis e da criação da tabela users no banco. Outros dois pontos importantes froam o middleware para auth via JWT e tambem usar o bcript para hashear a senha de uma forma bem mais segura.  

## T — Tests
Teve tanto testes manuais para validar o comportamento rodadno tudo localmente. Como também criamos tests para as novas apis de auth para cadastro e login

## O — Optimize
Acredito que a solução já esta bem otimizada e usando um padrão de authenticação bem recorrente no mercado que é a auth via JWT que é rapido para valdiar e também usamos refresh tokens e access tokens para não forçar o usuário a precisar logar de novo com email e senha a todos os momentos.  
Uma troca que acho que vale falar aqui é que usar o bcruipt para hashear a senha é um método que adiciona latência de 01 segundos na requisição mas é uma medida de segurança importante para caso os dados do banco sejam vazados. 
