    def _get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        사용자 정보 조회
        
        Args:
            user_id: 조회할 사용자의 ID
            
        Returns:
            사용자 정보 딕셔너리
        """
        try:
            response = self.client.users_info(user=user_id)
            if response and response.get('ok'):
                user = response.get('user', {})
                profile = user.get('profile', {})
                
                # 디스플레이 네임을 우선적으로 사용
                display_name = profile.get('display_name')
                if not display_name or display_name.strip() == '':
                    # 디스플레이 네임이 비어있으면 real_name 사용
                    display_name = profile.get('real_name') or user.get('real_name')
                    
                # 그래도 없으면, 기본 name 사용
                if not display_name or display_name.strip() == '':
                    display_name = user.get('name', '알 수 없음')
                
                return {
                    'id': user_id,
                    'name': display_name,
                    'profile': profile
                }
            return {'id': user_id, 'name': '알 수 없음', 'profile': {}}
        except SlackApiError as e:
            logger.error(f"사용자 정보 조회 실패: {str(e)}")
            return {'id': user_id, 'name': '알 수 없음', 'profile': {}}