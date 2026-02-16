using System;
using System.IO;
using Assets.Scripts;
using Assets.Scripts.Resources;
using UnityEditor;
using UnityEngine;
using static UnityEngine.GraphicsBuffer;

namespace AttributeHandlers
{
	public class Entity : AttributeHandler
	{
		public ushort m_flags = 0;
		public Guid128 ModelGuid;
		public Resource Resource;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{
					case 0:
						m_flags = (ushort)attr.Data.ToUInt32BigEndian();
						break;

					case 1:
					{
						reader.BaseStream.Position = attr.ReaderPosition + attr.Data.ToInt32BigEndian();
						ModelGuid = new Guid128(reader);
						break;
					}

					default:
						throw new NotImplementedException();
				}
			}
		}

		private void Start()
		{
			if (ModelGuid == null || ModelGuid.IsClear() || !ModelGuid.IsValid())
			{
				return;
			}

			Resource = ResourceHandlerManager.FindResourceById(ModelGuid);

			if (Resource == null)
			{
				Debug.LogError($"Couldn't find resource {ModelGuid} for {this}!");
				return;
			}

			if (Resource is MetaModel mm)
			{
				var metamodelinstance = new GameObject("MetaModel Instance");
				metamodelinstance.transform.parent = transform;
				metamodelinstance.transform.localPosition = Vector3.zero;
				metamodelinstance.transform.localRotation = Quaternion.identity;
				metamodelinstance.transform.localScale = Vector3.one;
				var comp = metamodelinstance.AddComponent<MetaModelInstance>();
				comp.Assign(mm);
			}
			else
			{
				throw new NotImplementedException($"{Resource.GetType().Name} in entity guid");
			}

			//Debug.Log($"Resource for {this} is of type {Resource.GetType().Name}");
		}

		private void OnDrawGizmos()
		{
			if (GetComponent<TriggerBase>() == null)
			{
				Gizmos.color = Color.blue;
				Gizmos.DrawWireSphere(transform.position, 0.25f);
			}
		}
	}
}