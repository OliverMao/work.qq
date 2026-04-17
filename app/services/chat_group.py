"""
企业微信群聊创建服务
"""

import logging
import json
import re
import uuid
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import SessionLocal
from app.db_models import ChatGroupRecord
from app.services.wecom_api import wecom_api_client

logger = logging.getLogger(__name__)


class ChatGroupService:
	"""封装企业微信创建群聊会话接口。"""

	@staticmethod
	def _normalize_userlist(userlist: List[str]) -> List[str]:
		users = [str(user).strip() for user in userlist if str(user).strip()]
		if len(users) < 2:
			raise ValueError("userlist 至少需要 2 个成员")
		if len(users) > 2000:
			raise ValueError("userlist 最多允许 2000 个成员")
		return users

	@staticmethod
	def _validate_chatid(chatid: Optional[str]) -> Optional[str]:
		if chatid is None:
			return None
		chatid = str(chatid).strip()
		if not chatid:
			return None
		if len(chatid) > 32:
			raise ValueError("chatid 最多 32 个字符")
		if not re.fullmatch(r"[0-9A-Za-z]+", chatid):
			raise ValueError("chatid 只允许 0-9、a-z、A-Z")
		return chatid

	@staticmethod
	def _sanitize_user_ids(user_ids: Optional[List[str]]) -> List[str]:
		if not user_ids:
			return []
		return [str(user).strip() for user in user_ids if str(user).strip()]

	@staticmethod
	def _validate_external_chat_id(chat_id: str) -> str:
		value = str(chat_id or "").strip()
		if not value:
			raise ValueError("chat_id 不能为空")
		return value

	def create_chat_group(
		self,
		userlist: List[str],
		name: Optional[str] = None,
		owner: Optional[str] = None
	) -> Dict[str, Any]:
		"""
		创建企业微信群聊会话。

		Args:
			userlist: 群成员 id 列表，至少 2 人，最多 2000 人
			name: 群聊名称，最多 50 个 utf8 字符
			owner: 群主 userid，不传则由企业微信随机选择
		"""
		token = wecom_api_client.get_access_token(secret=settings.app_secret)
		if not token:
			raise RuntimeError("无法获取企业微信 access_token")

		members = self._normalize_userlist(userlist)
		payload: Dict[str, Any] = {"userlist": members}

		if name:
			payload["name"] = str(name).strip()[:50]
		if owner:
			payload["owner"] = str(owner).strip()

		final_chatid = uuid.uuid4().hex
		payload["chatid"] = final_chatid

		url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/create?access_token={token}"
		try:
			resp = requests.post(url, json=payload, timeout=10)
			data = resp.json()
			if data.get("errcode") != 0:
				raise RuntimeError(f"创建群聊失败: {data}")

			db = SessionLocal()
			try:
				record = ChatGroupRecord(
					chatid=final_chatid,
					name=payload.get("name"),
					owner=payload.get("owner"),
					userlist_json=json.dumps(members, ensure_ascii=False),
				)
				db.add(record)
				db.commit()
			except SQLAlchemyError as db_err:
				db.rollback()
				raise RuntimeError(f"群聊创建成功但写入本地数据库失败: {db_err}") from db_err
			finally:
				db.close()

			return data
		except Exception as e:
			logger.exception("创建群聊会话失败")
			raise RuntimeError(f"创建群聊会话异常: {e}") from e

	def list_all_chat_groups(self) -> List[Dict[str, Any]]:
		"""读取本地数据库中的全部群聊记录。"""
		db = SessionLocal()
		try:
			records = (
				db.query(ChatGroupRecord)
				.order_by(ChatGroupRecord.created_at.desc())
				.all()
			)
			result: List[Dict[str, Any]] = []
			for item in records:
				result.append(
					{
						"chatid": item.chatid,
						"name": item.name,
						"owner": item.owner,
						"userlist": json.loads(item.userlist_json),
						"chat_type": item.chat_type,
						"created_at": item.created_at.isoformat() if item.created_at else None,
					}
				)
			return result
		except SQLAlchemyError as db_err:
			logger.exception("读取群聊列表失败")
			raise RuntimeError(f"读取群聊列表失败: {db_err}") from db_err
		finally:
			db.close()

	def get_chat_group_and_sync(self, chatid: str) -> Dict[str, Any]:
		"""从企业微信获取群聊信息，并同步到本地数据库。"""
		validated_chatid = self._validate_chatid(chatid)
		if not validated_chatid:
			raise ValueError("chatid 不能为空")

		token = wecom_api_client.get_access_token(secret=settings.app_secret)
		if not token:
			raise RuntimeError("无法获取企业微信 access_token")

		url = (
			"https://qyapi.weixin.qq.com/cgi-bin/appchat/get"
			f"?access_token={token}&chatid={validated_chatid}"
		)

		try:
			resp = requests.get(url, timeout=10)
			data = resp.json()
			if data.get("errcode") != 0:
				raise RuntimeError(f"获取群聊会话失败: {data}")

			chat_info = data.get("chat_info") or {}
			members = self._sanitize_user_ids(chat_info.get("userlist") or [])

			db = SessionLocal()
			try:
				record = (
					db.query(ChatGroupRecord)
					.filter(ChatGroupRecord.chatid == validated_chatid)
					.first()
				)

				if not record:
					record = ChatGroupRecord(
						chatid=validated_chatid,
						name=chat_info.get("name"),
						owner=chat_info.get("owner"),
						userlist_json=json.dumps(members, ensure_ascii=False),
						chat_type=chat_info.get("chat_type"),
					)
					db.add(record)
				else:
					record.name = chat_info.get("name")
					record.owner = chat_info.get("owner")
					record.userlist_json = json.dumps(members, ensure_ascii=False)
					record.chat_type = chat_info.get("chat_type")

				db.commit()
			except SQLAlchemyError as db_err:
				db.rollback()
				raise RuntimeError(f"获取群聊成功但同步本地数据库失败: {db_err}") from db_err
			finally:
				db.close()

			return data
		except Exception as e:
			logger.exception("获取并同步群聊会话失败")
			raise RuntimeError(f"获取并同步群聊会话异常: {e}") from e

	def update_chat_group(
		self,
		chatid: str,
		name: Optional[str] = None,
		owner: Optional[str] = None,
		add_user_list: Optional[List[str]] = None,
		del_user_list: Optional[List[str]] = None,
	) -> Dict[str, Any]:
		"""修改企业微信群聊，并同步更新本地数据库记录。"""
		validated_chatid = self._validate_chatid(chatid)
		if not validated_chatid:
			raise ValueError("chatid 不能为空")

		add_users = self._sanitize_user_ids(add_user_list)
		del_users = self._sanitize_user_ids(del_user_list)
		has_update_field = bool(
			(name and str(name).strip())
			or (owner and str(owner).strip())
			or add_users
			or del_users
		)
		if not has_update_field:
			raise ValueError("name、owner、add_user_list、del_user_list 至少传一个")

		token = wecom_api_client.get_access_token(secret=settings.app_secret)
		if not token:
			raise RuntimeError("无法获取企业微信 access_token")

		payload: Dict[str, Any] = {"chatid": validated_chatid}
		if name and str(name).strip():
			payload["name"] = str(name).strip()[:50]
		if owner and str(owner).strip():
			payload["owner"] = str(owner).strip()
		if add_users:
			payload["add_user_list"] = add_users
		if del_users:
			payload["del_user_list"] = del_users

		url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/update?access_token={token}"
		try:
			resp = requests.post(url, json=payload, timeout=10)
			data = resp.json()
			if data.get("errcode") != 0:
				raise RuntimeError(f"修改群聊失败: {data}")

			db = SessionLocal()
			try:
				record = (
					db.query(ChatGroupRecord)
					.filter(ChatGroupRecord.chatid == validated_chatid)
					.first()
				)

				if record:
					if "name" in payload:
						record.name = payload["name"]
					if "owner" in payload:
						record.owner = payload["owner"]

					current_users = set(json.loads(record.userlist_json or "[]"))
					current_users.update(add_users)
					current_users.difference_update(del_users)
					record.userlist_json = json.dumps(sorted(current_users), ensure_ascii=False)
				else:
					base_users = set(add_users)
					base_users.difference_update(del_users)
					record = ChatGroupRecord(
						chatid=validated_chatid,
						name=payload.get("name"),
						owner=payload.get("owner"),
						userlist_json=json.dumps(sorted(base_users), ensure_ascii=False),
					)
					db.add(record)

				db.commit()
			except SQLAlchemyError as db_err:
				db.rollback()
				raise RuntimeError(f"群聊修改成功但同步本地数据库失败: {db_err}") from db_err
			finally:
				db.close()

			return data
		except Exception as e:
			logger.exception("修改群聊会话失败")
			raise RuntimeError(f"修改群聊会话异常: {e}") from e

	def delete_chat_group(self, chatid: str) -> Dict[str, Any]:
		"""仅删除本地数据库中的群聊记录，不调用企业微信删除接口。"""
		validated_chatid = self._validate_chatid(chatid)
		if not validated_chatid:
			raise ValueError("chatid 不能为空")

		db = SessionLocal()
		try:
			record = (
				db.query(ChatGroupRecord)
				.filter(ChatGroupRecord.chatid == validated_chatid)
				.first()
			)
			if not record:
				return {"chatid": validated_chatid, "deleted": False}

			db.delete(record)
			db.commit()
			return {"chatid": validated_chatid, "deleted": True}
		except SQLAlchemyError as db_err:
			db.rollback()
			logger.exception("删除群聊记录失败")
			raise RuntimeError(f"删除群聊记录失败: {db_err}") from db_err
		finally:
			db.close()

	def send_markdown_message(self, chatid: str, content: str) -> Dict[str, Any]:
		"""向指定群聊发送 markdown 消息。"""
		validated_chatid = self._validate_chatid(chatid)
		if not validated_chatid:
			raise ValueError("chatid 不能为空")

		final_content = str(content).strip()
		if not final_content:
			raise ValueError("content 不能为空")
		if len(final_content.encode("utf-8")) > 2048:
			raise ValueError("content 最长不超过 2048 字节")

		token = wecom_api_client.get_access_token(secret=settings.app_secret)
		if not token:
			raise RuntimeError("无法获取企业微信 access_token")

		payload = {
			"chatid": validated_chatid,
			"msgtype": "markdown",
			"markdown": {"content": final_content},
		}
		url = f"https://qyapi.weixin.qq.com/cgi-bin/appchat/send?access_token={token}"

		try:
			resp = requests.post(url, json=payload, timeout=10)
			data = resp.json()
			if data.get("errcode") != 0:
				raise RuntimeError(f"发送 markdown 消息失败: {data}")
			return data
		except Exception as e:
			logger.exception("发送 markdown 消息失败")
			raise RuntimeError(f"发送 markdown 消息异常: {e}") from e

	def batch_sync_chat_groups_from_cloud(self) -> Dict[str, Any]:
		"""批量从企业微信云端拉取群信息，并覆盖同步到本地数据库。"""
		db = SessionLocal()
		try:
			chatids = [item.chatid for item in db.query(ChatGroupRecord.chatid).all()]
		except SQLAlchemyError as db_err:
			logger.exception("读取本地群聊列表失败")
			raise RuntimeError(f"读取本地群聊列表失败: {db_err}") from db_err
		finally:
			db.close()

		if not chatids:
			return {
				"total": 0,
				"success": 0,
				"failed": 0,
				"items": [],
			}

		results: List[Dict[str, Any]] = []
		success_count = 0
		failed_count = 0

		for cid in chatids:
			try:
				self.get_chat_group_and_sync(chatid=cid)
				success_count += 1
				results.append({"chatid": cid, "synced": True})
			except Exception as err:
				failed_count += 1
				results.append({"chatid": cid, "synced": False, "error": str(err)})

		return {
			"total": len(chatids),
			"success": success_count,
			"failed": failed_count,
			"items": results,
		}

	def get_customer_group_detail(self, chat_id: str, need_name: int = 0) -> Dict[str, Any]:
		"""获取客户群详情（externalcontact/groupchat/get）。"""
		validated_chat_id = self._validate_external_chat_id(chat_id)

		if need_name not in (0, 1):
			raise ValueError("need_name 只允许 0 或 1")

		secret = settings.wecom_contact_secret or settings.app_secret
		token = wecom_api_client.get_access_token(secret=secret)
		if not token:
			raise RuntimeError("无法获取客户联系 access_token")

		payload: Dict[str, Any] = {
			"chat_id": validated_chat_id,
			"need_name": int(need_name),
		}
		url = (
			"https://qyapi.weixin.qq.com/cgi-bin/externalcontact/groupchat/get"
			f"?access_token={token}"
		)

		try:
			resp = requests.post(url, json=payload, timeout=10)
			data = resp.json()
		except Exception as e:
			logger.exception("调用 externalcontact/groupchat/get 接口异常")
			raise RuntimeError(f"调用 externalcontact/groupchat/get 接口异常: {e}") from e

		if data.get("errcode") != 0:
			raise RuntimeError(f"获取客户群详情失败: {data}")

		return data


chat_group_service = ChatGroupService()
