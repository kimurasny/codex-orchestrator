using System;

namespace Sample.BL.Common
{
    /// <summary>
    /// ログイン認証に関する業務ロジックを提供するサンプルクラス。
    /// </summary>
    public class LoginService
    {
        private readonly IUserRepository _userRepository;

        public LoginService(IUserRepository userRepository)
        {
            _userRepository = userRepository;
        }

        /// <summary>
        /// ユーザー名とパスワードを検証しログイン可否を返す。
        /// </summary>
        public bool Authenticate(string userName, string password)
        {
            var user = _userRepository.FindByName(userName);
            if (user == null)
            {
                return false;
            }
            return user.VerifyPassword(password);
        }
    }
}
