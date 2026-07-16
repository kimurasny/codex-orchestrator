using System;
using System.Collections.Generic;

namespace Sample.BL.Common
{
    /// <summary>
    /// ユーザー情報の登録・取得を行うサンプルクラス。
    /// </summary>
    public class UserService
    {
        private readonly IUserRepository _userRepository;

        public UserService(IUserRepository userRepository)
        {
            _userRepository = userRepository;
        }

        /// <summary>
        /// 新規ユーザーを登録する。
        /// </summary>
        public void Register(string userName, string email)
        {
            if (string.IsNullOrWhiteSpace(userName))
            {
                throw new ArgumentException("ユーザー名は必須です", nameof(userName));
            }
            _userRepository.Save(new User(userName, email));
        }

        /// <summary>
        /// 全ユーザーを取得する。
        /// </summary>
        public IReadOnlyList<User> GetAll()
        {
            return _userRepository.FindAll();
        }
    }
}
