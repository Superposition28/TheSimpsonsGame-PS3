using Assets.Scripts.Resources;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using UnityEngine;

namespace Assets.Scripts.AttributeHandlers
{
    class ZoneRender : AttributeHandler
    {
	    public uint Unk_0;
	    public uint Unk_1;
	    public uint Unk_2;
	    public uint Unk_3;
	    public uint Unk_4;
	    public float Unk_5;
	    public string Unk_6;
	    public string Unk_7;

		public override void HandleAttributes(BinaryReader reader, SimGroup.AttrPacket attrPacket)
		{
			foreach (var attr in attrPacket.Attributes)
			{
				switch (attr.Index)
				{

				}
			}
		}

		private void Start()
		{
			// TODO: work out actual way of doing this
			var metaModel = ResourceHandlerManager.GetResources<MetaModel>().First(x => x.STRFile == STRFile && x.m_uSourcePath == 0 && x.m_nVariables == 0);

			var metamodelinstance = new GameObject("MetaModel Instance");
			metamodelinstance.transform.parent = transform;
			metamodelinstance.transform.localPosition = Vector3.zero;
			metamodelinstance.transform.localRotation = Quaternion.identity;
			metamodelinstance.transform.localScale = Vector3.one;
			var comp = metamodelinstance.AddComponent<MetaModelInstance>();
			comp.Assign(metaModel);
		}
	}
}
